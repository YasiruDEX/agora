"""LangGraph runnable for the Citizen Inquiry Agent.

Builds a StateGraph over `messages` that calls an LLM bound to the
`search_knowledge_base` MCP tool, served remotely over SSE by a standalone
local-kb MCP server (see mcp_servers/local_kb_mcp/server.py, run with
MCP_TRANSPORT=sse), grounded in this department's KB_NAMESPACE, with
MemorySaver checkpointing keyed by session_id.

This agent container does not run the MCP server itself — it only holds its
network address (KB_MCP_URL), configured via an environment variable.

FALLBACK BEHAVIOR: the agent must boot even if the local-kb MCP server is
unreachable at startup (e.g. not deployed yet, mid-restart, network blip). If
connecting fails, build_graph() binds a stub tool instead of raising, so the
FastAPI app still comes up and /chat still responds -- just with a clear
"MCP server not available" message instead of grounded KB content. The same
fallback also covers the MCP server going down *after* a successful startup
(the real tool's call is wrapped too), since langchain_mcp_adapters only
actually opens the SSE connection when the tool is invoked, not at get_tools()
time.
"""
import logging
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

logger = logging.getLogger("citizen_inquiry_agent.graph")

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent.parent
PROMPT_PATH = AGENT_DIR / "prompt.md"

# Shared infra secrets (OPENAI_API_KEY) live in the root .env.
# Agent-specific department config lives in this agent's own .env and takes
# precedence over anything (accidentally) duplicated at the root.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(AGENT_DIR / ".env", override=True)

# Remote MCP server endpoint. Read AFTER load_dotenv() so a URL set in either
# .env file actually takes effect. Defaults assume the server is running
# locally for testing (`MCP_TRANSPORT=sse` on mcp_servers/local_kb_mcp/server.py);
# in a real deployment this is injected by the platform (e.g. pointed at an
# Agent Manager MCP proxy in front of the server).
KB_MCP_URL = os.environ.get("KB_MCP_URL", "http://localhost:9001/sse")

REQUIRED_ENV = [
    "OPENAI_API_KEY",
    "DEPARTMENT_NAME",
    "KB_NAMESPACE",
    "WELCOME_MESSAGE",
    "SUPPORT_EMAIL_CONTACT",
    "OFFICE_HOURS_INFO",
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


def mcp_unavailable_message() -> str:
    support_email = os.environ.get("SUPPORT_EMAIL_CONTACT", "the department")
    return (
        "Whoa, hold on!! The knowledge base service (MCP server) is not available "
        "right now!! I can't look up department documents, fees, or procedures until "
        f"it's back. Please try again shortly, or contact {support_email} in the meantime."
    )


def _fallback_kb_tool(namespace: str) -> StructuredTool:
    """Stub tool used whenever the local-kb MCP server can't be reached -- at
    startup or mid-session. Always returns the same "MCP server not available"
    message so the agent keeps responding instead of crashing or hanging."""

    async def _unavailable(query: str, top_k: int = 5) -> str:
        return mcp_unavailable_message()

    return StructuredTool.from_function(
        coroutine=_unavailable,
        name="search_knowledge_base",
        description=(
            f"Semantic search over the '{namespace}' department knowledge base. "
            "Always use this to answer factual citizen questions about documents, "
            "fees, timelines, eligibility, or procedures."
        ),
        args_schema=SearchKnowledgeBaseArgs,
    )


async def _load_kb_tool() -> StructuredTool:
    """Connect to the local-kb MCP server and wrap search_knowledge_base.

    The wrapper hard-pins `namespace` to this department's KB_NAMESPACE env var so
    the tool always searches the correct department's data, regardless of what the
    LLM would otherwise pass.

    Never raises: if the MCP server can't be reached (now, or later when the
    wrapped tool is actually invoked), the agent still boots/responds -- it just
    falls back to a fixed "MCP server not available" message instead of
    grounded KB content. See the module docstring for why both paths need
    covering separately.
    """
    namespace = os.environ["KB_NAMESPACE"]

    client = MultiServerMCPClient(
        {
            "local-kb": {
                "url": KB_MCP_URL,
                "transport": "sse",
            }
        }
    )

    try:
        mcp_tools = await client.get_tools()
        raw_tool = next(t for t in mcp_tools if t.name == "search_knowledge_base")
    except Exception:
        logger.warning(
            "Could not reach local-kb MCP server at %s -- falling back to a "
            "'MCP server not available' response for search_knowledge_base.",
            KB_MCP_URL,
            exc_info=True,
        )
        return _fallback_kb_tool(namespace)

    async def _search(query: str, top_k: int = 5) -> str:
        try:
            raw_result = await raw_tool.ainvoke({"namespace": namespace, "query": query, "top_k": top_k})
        except Exception:
            logger.warning(
                "local-kb MCP server at %s became unreachable during a search_knowledge_base call.",
                KB_MCP_URL,
                exc_info=True,
            )
            return mcp_unavailable_message()
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
