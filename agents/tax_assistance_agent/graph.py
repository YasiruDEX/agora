"""LangGraph runnable for the Tax & Assessment Agent.

Dynamically discovers tools from THREE remote MCP servers (pinecone-kb,
tax-db-mcp, payment-mcp) over SSE, pins the Pinecone tool's namespace to this
department's KB_NAMESPACE, and binds an agent-to-agent tool that forwards
out-of-scope questions to a running Citizen Inquiry Agent instance over HTTP.

This agent container does not run the MCP servers itself — it only holds
their network addresses (PINECONE_MCP_URL, TAX_DB_MCP_URL, PAYMENT_MCP_URL),
configured via environment variables. The MCP servers and their databases are
deployed and scaled independently (see mcp_servers/*/server.py, run with
MCP_TRANSPORT=sse).
"""
import logging
import os
import string
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, Field

from langchain_mcp_adapters.client import MultiServerMCPClient

# This absolute import only resolves when the full monorepo layout is present
# (agents/ as an importable package alongside mcp_servers/, data/, etc). Some
# deployment platforms instead package this agent's own directory in
# isolation as the process's working directory — in that case `agents` never
# exists, but `tools.py` sits right next to this file and imports directly.
try:
    from agents.tax_assistance_agent.tools import consult_citizen_inquiry_agent
except ModuleNotFoundError:
    from tools import consult_citizen_inquiry_agent  # type: ignore[no-redef]

logger = logging.getLogger("tax_assistance_agent.graph")

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent.parent
PROMPT_PATH = AGENT_DIR / "prompt.md"

# Shared infra secrets (PINECONE_*, OPENAI_API_KEY) live in the root .env.
# Agent-specific department config lives in this agent's own .env and takes
# precedence over anything (accidentally) duplicated at the root.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(AGENT_DIR / ".env", override=True)

# Remote MCP server endpoints. Read AFTER load_dotenv() so a URL set in
# either .env file actually takes effect. Defaults assume each server is
# running locally for testing (`MCP_TRANSPORT=sse` on mcp_servers/*/server.py);
# in a real deployment these are injected by the platform (e.g. pointed at an
# Agent Manager MCP proxy in front of each server).
PINECONE_MCP_URL = os.environ.get("PINECONE_MCP_URL", "http://localhost:9001/sse")
TAX_DB_MCP_URL = os.environ.get("TAX_DB_MCP_URL", "http://localhost:9005/sse")
PAYMENT_MCP_URL = os.environ.get("PAYMENT_MCP_URL", "http://localhost:9006/sse")

REQUIRED_ENV = [
    "OPENAI_API_KEY",
    "DEPARTMENT_NAME",
    "KB_NAMESPACE",
    "WELCOME_MESSAGE",
    "SUPPORT_EMAIL_CONTACT",
    "OFFICE_HOURS_INFO",
    "PROMPT_PAYMENT_DISCOUNT_PCT",
    "LATE_PAYMENT_SURCHARGE_PCT",
    "PINECONE_API_KEY",
    "PINECONE_INDEX_NAME",
]


class TaxAgentState(MessagesState):
    """Extends MessagesState with session_id so tools can access it via InjectedState."""

    session_id: str


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
        PROMPT_PAYMENT_DISCOUNT_PCT=os.environ["PROMPT_PAYMENT_DISCOUNT_PCT"],
        LATE_PAYMENT_SURCHARGE_PCT=os.environ["LATE_PAYMENT_SURCHARGE_PCT"],
    )


class SearchKnowledgeBaseArgs(BaseModel):
    query: str = Field(description="Natural language citizen question to search for.")
    top_k: int = Field(default=5, description="Number of matching chunks to return.")


async def _discover_mcp_tools() -> list:
    """Connect to all three MCP servers and dynamically discover their tools."""
    client = MultiServerMCPClient(
        {
            "pinecone-kb": {
                "url": PINECONE_MCP_URL,
                "transport": "sse",
            },
            "tax-db-mcp": {
                "url": TAX_DB_MCP_URL,
                "transport": "sse",
            },
            "payment-mcp": {
                "url": PAYMENT_MCP_URL,
                "transport": "sse",
            },
        }
    )
    tools = await client.get_tools()
    logger.info("Discovered %d MCP tool(s): %s", len(tools), [t.name for t in tools])
    return tools


def _wrap_kb_tool_with_pinned_namespace(raw_tool, namespace: str) -> StructuredTool:
    """Hide `namespace` from the LLM and hard-pin it to this department's KB_NAMESPACE."""

    async def _search(query: str, top_k: int = 5) -> str:
        raw_result = await raw_tool.ainvoke({"namespace": namespace, "query": query, "top_k": top_k})
        return _extract_text(raw_result)

    return StructuredTool.from_function(
        coroutine=_search,
        name="search_knowledge_base",
        description=(
            f"Semantic search over the '{namespace}' department policy knowledge base. "
            "Use this for assessment rate policy, trade tax tiers, non-arrears certificate "
            "procedure, and discount/surcharge period rules."
        ),
        args_schema=SearchKnowledgeBaseArgs,
    )


async def build_graph():
    """Build and compile the LangGraph runnable. Call once per process."""
    _require_env()

    system_prompt = build_system_prompt()
    namespace = os.environ["KB_NAMESPACE"]

    mcp_tools = await _discover_mcp_tools()
    kb_tool = next(t for t in mcp_tools if t.name == "search_knowledge_base")
    other_tools = [t for t in mcp_tools if t.name != "search_knowledge_base"]

    tools = [
        _wrap_kb_tool_with_pinned_namespace(kb_tool, namespace),
        *other_tools,
        consult_citizen_inquiry_agent,
    ]
    logger.info("Bound %d tool(s) to the agent: %s", len(tools), [t.name for t in tools])

    llm = ChatOpenAI(
        model=os.environ.get("LLM_MODEL_NAME", "gpt-4o"),
        temperature=float(os.environ.get("MODEL_TEMPERATURE", "0.1")),
        max_tokens=int(os.environ.get("MAX_TOKENS", "1000")),
        api_key=os.environ["OPENAI_API_KEY"],
    ).bind_tools(tools)

    async def call_model(state: TaxAgentState):
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    graph = StateGraph(TaxAgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
