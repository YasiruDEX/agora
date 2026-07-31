"""LangGraph runnable for the Citizen Inquiry Agent.

Builds a StateGraph over `messages` that calls an LLM bound to the
`search_knowledge_base` MCP tool, served remotely over SSE by a standalone
pinecone-kb MCP server (see mcp_servers/pinecone_kb_mcp/server.py, run with
MCP_TRANSPORT=sse), grounded in this department's KB_NAMESPACE, with
MemorySaver checkpointing keyed by session_id.

This agent container does not run the MCP server itself — it only holds its
network address (PINECONE_MCP_URL), configured via an environment variable.
"""
import os
import string
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, MessagesState, END
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, Field

from langchain_mcp_adapters.client import MultiServerMCPClient  # noqa: E402

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent.parent
PROMPT_PATH = AGENT_DIR / "prompt.md"

# Shared infra secrets (PINECONE_*, OPENAI_API_KEY) live in the root .env.
# Agent-specific department config lives in this agent's own .env and takes
# precedence over anything (accidentally) duplicated at the root.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(AGENT_DIR / ".env", override=True)

# Remote MCP server endpoint. Read AFTER load_dotenv() so a URL set in either
# .env file actually takes effect. Defaults assume the server is running
# locally for testing (`MCP_TRANSPORT=sse` on mcp_servers/pinecone_kb_mcp/server.py);
# in a real deployment this is injected by the platform (e.g. pointed at an
# Agent Manager MCP proxy in front of the server).
PINECONE_MCP_URL = os.environ.get("PINECONE_MCP_URL", "http://localhost:9001/sse")

REQUIRED_ENV = [
    "OPENAI_API_KEY",
    "DEPARTMENT_NAME",
    "KB_NAMESPACE",
    "WELCOME_MESSAGE",
    "SUPPORT_EMAIL_CONTACT",
    "OFFICE_HOURS_INFO",
    "PINECONE_API_KEY",
    "PINECONE_INDEX_NAME",
]


def _require_env() -> None:
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def _extract_text(raw_result: Any) -> str:
    """Normalizes output from langchain_mcp_adapters tool execution into a clean string.

    Handles string, list of strings, list of objects/dicts, and TextContent blocks.
    """
    if isinstance(raw_result, str):
        return raw_result

    if isinstance(raw_result, list):
        extracted = []
        for item in raw_result:
            if isinstance(item, str):
                extracted.append(item)
            elif hasattr(item, "text"):  # TextContent block
                extracted.append(item.text)
            elif isinstance(item, dict) and "text" in item:
                extracted.append(item["text"])
            else:
                extracted.append(str(item))
        return "\n".join(extracted)

    if hasattr(raw_result, "text"):
        return raw_result.text

    return str(raw_result)


def build_system_prompt() -> str:
    template = string.Template(PROMPT_PATH.read_text(encoding="utf-8"))
    return template.safe_substitute(
        DEPARTMENT_NAME=os.environ["DEPARTMENT_NAME"],
        DEPARTMENT_CODE=os.environ.get("DEPARTMENT_CODE", ""),
        KB_NAMESPACE=os.environ["KB_NAMESPACE"],
        WELCOME_MESSAGE=os.environ["WELCOME_MESSAGE"],
        SUPPORT_EMAIL_CONTACT=os.environ["SUPPORT_EMAIL_CONTACT"],
        OFFICE_HOURS_INFO=os.environ["OFFICE_HOURS_INFO"],
    )


class SearchKnowledgeBaseArgs(BaseModel):
    query: str = Field(description="Natural language citizen question to search for.")
    top_k: int = Field(default=5, description="Number of matching chunks to return.")


async def _load_kb_tool() -> StructuredTool:
    """Connect to the pinecone-kb MCP server and wrap search_knowledge_base.

    The wrapper hard-pins `namespace` to this department's KB_NAMESPACE env var so
    the tool always searches the correct department's data, regardless of what the
    LLM would otherwise pass.
    """
    namespace = os.environ["KB_NAMESPACE"]

    client = MultiServerMCPClient(
        {
            "pinecone-kb": {
                "url": PINECONE_MCP_URL,
                "transport": "sse",
            }
        }
    )
    mcp_tools = await client.get_tools()
    raw_tool = next(t for t in mcp_tools if t.name == "search_knowledge_base")

    async def _search(query: str, top_k: int = 5) -> str:
        raw_result = await raw_tool.ainvoke({"namespace": namespace, "query": query, "top_k": top_k})
        return _extract_text(raw_result)

    return StructuredTool.from_function(
        coroutine=_search,
        name="search_knowledge_base",
        description=(
            f"Semantic search over the '{namespace}' department knowledge base. "
            "Always use this to answer factual citizen questions about documents, "
            "fees, timelines, eligibility, or procedures."
        ),
        args_schema=SearchKnowledgeBaseArgs,
    )


async def build_graph():
    """Build and compile the LangGraph runnable. Call once per process."""
    _require_env()

    system_prompt = build_system_prompt()
    kb_tool = await _load_kb_tool()
    tools = [kb_tool]

    llm = ChatOpenAI(
        model=os.environ.get("LLM_MODEL_NAME", "gpt-4o"),
        temperature=float(os.environ.get("MODEL_TEMPERATURE", "0.1")),
        max_tokens=int(os.environ.get("MAX_TOKENS", "1000")),
        api_key=os.environ["OPENAI_API_KEY"],
    ).bind_tools(tools)

    async def call_model(state: MessagesState):
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
