"""LangGraph runnable for the Permit & Licensing Agent.

Dynamically discovers tools from two MCP servers (pinecone-kb, permit-db-mcp),
pins the Pinecone tool's namespace to this department's KB_NAMESPACE, and binds
an agent-to-agent tool that forwards out-of-scope questions to a running
Citizen Inquiry Agent instance over HTTP.
"""
import logging
import os
import string
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, Field

from langchain_mcp_adapters.client import MultiServerMCPClient

from agents.permit_licensing_agent.tools import consult_citizen_inquiry_agent

logger = logging.getLogger("permit_licensing_agent.graph")

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent.parent
PROMPT_PATH = AGENT_DIR / "prompt.md"
PINECONE_MCP_SERVER_PATH = REPO_ROOT / "mcp_servers" / "pinecone_kb_mcp" / "server.py"
PERMIT_DB_MCP_SERVER_PATH = REPO_ROOT / "mcp_servers" / "permit_db_mcp" / "server.py"

# Which agent-local env file to load. Defaults to ".env" (single-instance mode).
# Set AGENT_ENV_FILE=".env.building_permits" (etc.) in the process environment
# *before* launch to run this codebase as a distinct, independently-configured
# instance (its own port, department identity, and PERMIT_DB_PATH).
AGENT_ENV_FILE = os.environ.get("AGENT_ENV_FILE", ".env")

# Shared infra secrets (PINECONE_*, OPENAI_API_KEY) live in the root .env.
# Agent-specific department config lives in this agent's own env file and
# takes precedence over anything (accidentally) duplicated at the root.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(AGENT_DIR / AGENT_ENV_FILE, override=True)

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


class PermitAgentState(MessagesState):
    """Extends MessagesState with session_id so tools can access it via InjectedState."""

    session_id: str


def _require_env() -> None:
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def build_system_prompt() -> str:
    template = string.Template(PROMPT_PATH.read_text(encoding="utf-8"))
    prompt = template.safe_substitute(
        DEPARTMENT_NAME=os.environ["DEPARTMENT_NAME"],
        DEPARTMENT_CODE=os.environ.get("DEPARTMENT_CODE", ""),
        KB_NAMESPACE=os.environ["KB_NAMESPACE"],
        WELCOME_MESSAGE=os.environ["WELCOME_MESSAGE"],
        SUPPORT_EMAIL_CONTACT=os.environ["SUPPORT_EMAIL_CONTACT"],
        OFFICE_HOURS_INFO=os.environ["OFFICE_HOURS_INFO"],
    )

    permit_category = os.environ.get("PERMIT_CATEGORY")
    if permit_category:
        prompt += (
            f"\n\n# Instance scope\n\n"
            f"This instance of the Permit & Licensing Assistant handles **{permit_category}** "
            f"applications only. Its database only contains records of that type. If a citizen "
            f"asks about a different permit type, say clearly that this instance handles "
            f"{permit_category} only and, where helpful, still answer general policy questions "
            f"from the knowledge base — or use `consult_citizen_inquiry_agent` if it's truly "
            f"outside permits and licensing altogether."
        )
    return prompt


class SearchKnowledgeBaseArgs(BaseModel):
    query: str = Field(description="Natural language citizen question to search for.")
    top_k: int = Field(default=5, description="Number of matching chunks to return.")


async def _discover_mcp_tools() -> list:
    """Connect to both MCP servers and dynamically discover their tools."""
    client = MultiServerMCPClient(
        {
            "pinecone-kb": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(PINECONE_MCP_SERVER_PATH)],
                "env": dict(os.environ),
            },
            "permit-db-mcp": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(PERMIT_DB_MCP_SERVER_PATH)],
                "env": dict(os.environ),
            },
        }
    )
    tools = await client.get_tools()
    logger.info("Discovered %d MCP tool(s): %s", len(tools), [t.name for t in tools])
    return tools


def _wrap_kb_tool_with_pinned_namespace(raw_tool, namespace: str) -> StructuredTool:
    """Hide `namespace` from the LLM and hard-pin it to this department's KB_NAMESPACE."""

    async def _search(query: str, top_k: int = 5) -> str:
        return await raw_tool.ainvoke({"namespace": namespace, "query": query, "top_k": top_k})

    return StructuredTool.from_function(
        coroutine=_search,
        name="search_knowledge_base",
        description=(
            f"Semantic search over the '{namespace}' department policy knowledge base. "
            "Use this for building plan, street line certificate, and trade license "
            "requirements, fees, and procedures."
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
    db_tools = [t for t in mcp_tools if t.name.startswith("db_")]

    tools = [
        _wrap_kb_tool_with_pinned_namespace(kb_tool, namespace),
        *db_tools,
        consult_citizen_inquiry_agent,
    ]
    logger.info("Bound %d tool(s) to the agent: %s", len(tools), [t.name for t in tools])

    llm = ChatOpenAI(
        model=os.environ.get("LLM_MODEL_NAME", "gpt-4o"),
        temperature=float(os.environ.get("MODEL_TEMPERATURE", "0.1")),
        max_tokens=int(os.environ.get("MAX_TOKENS", "1000")),
        api_key=os.environ["OPENAI_API_KEY"],
    ).bind_tools(tools)

    async def call_model(state: PermitAgentState):
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    graph = StateGraph(PermitAgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
