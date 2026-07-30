"""LangGraph runnable for the Central Portal Chat Agent.

The primary AI assistant on the main gov.lk / gic.gov.lk portal home page.
Unlike every department agent (which pins search_knowledge_base to one
KB_NAMESPACE), this agent binds search_all_government_knowledge -- a fan-out
wrapper (see tools.py) over the same pinecone-kb MCP tool that searches every
configured department namespace (or one, if the citizen's question clearly
names a department) and reports back which namespace(s) contributed.
"""
import logging
import os
import string
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_mcp_adapters.client import MultiServerMCPClient

from agents.central_portal_agent.tools import build_search_all_government_knowledge_tool

logger = logging.getLogger("central_portal_agent.graph")

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent.parent
PROMPT_PATH = AGENT_DIR / "prompt.md"
PINECONE_MCP_SERVER_PATH = REPO_ROOT / "mcp_servers" / "pinecone_kb_mcp" / "server.py"

# Shared infra secrets (PINECONE_*, OPENAI_API_KEY) live in the root .env.
# Agent-specific config lives in this agent's own .env and takes precedence
# over anything (accidentally) duplicated at the root.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(AGENT_DIR / ".env", override=True)

REQUIRED_ENV = [
    "OPENAI_API_KEY",
    "DEPARTMENT_NAME",
    "ALL_NAMESPACES",
    "WELCOME_MESSAGE",
    "SUPPORT_EMAIL_CONTACT",
    "OFFICE_HOURS_INFO",
    "PINECONE_API_KEY",
    "PINECONE_INDEX_NAME",
]

LANGUAGE_NAMES = {"en": "English", "si": "Sinhala", "ta": "Tamil"}


class CentralPortalState(MessagesState):
    """Extends MessagesState with the per-request language, read by call_model
    each turn. (Which namespace(s) contributed to an answer is derived by
    main.py from the tool messages themselves, not carried as graph state --
    see tools.py's module docstring for why.)"""

    language: str


def _require_env() -> None:
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def _all_namespaces() -> list[str]:
    return [n.strip() for n in os.environ["ALL_NAMESPACES"].split(",") if n.strip()]


def build_system_prompt() -> str:
    template = string.Template(PROMPT_PATH.read_text(encoding="utf-8"))
    return template.safe_substitute(
        DEPARTMENT_NAME=os.environ["DEPARTMENT_NAME"],
        DEPARTMENT_CODE=os.environ.get("DEPARTMENT_CODE", ""),
        ALL_NAMESPACES=", ".join(_all_namespaces()),
        WELCOME_MESSAGE=os.environ["WELCOME_MESSAGE"],
        SUPPORT_EMAIL_CONTACT=os.environ["SUPPORT_EMAIL_CONTACT"],
        OFFICE_HOURS_INFO=os.environ["OFFICE_HOURS_INFO"],
    )


def _language_instruction(language: str) -> str:
    name = LANGUAGE_NAMES.get(language, "English")
    if name == "English":
        return "MANDATORY RESPONSE LANGUAGE: English. Write your entire reply in English."
    return (
        f"MANDATORY RESPONSE LANGUAGE: {name}. Write your entire reply in {name} script, "
        f"including the greeting -- not English, regardless of what language the persona "
        f"instructions below are written in. Only fall back to English if you are not "
        f"confident writing accurately in {name}, and if so say so plainly in English."
    )


async def _discover_mcp_tools() -> list:
    """Connect to the pinecone-kb MCP server and dynamically discover its tools."""
    client = MultiServerMCPClient(
        {
            "pinecone-kb": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(PINECONE_MCP_SERVER_PATH)],
                "env": dict(os.environ),
            }
        }
    )
    tools = await client.get_tools()
    logger.info("Discovered %d MCP tool(s): %s", len(tools), [t.name for t in tools])
    return tools


async def build_graph():
    """Build and compile the LangGraph runnable. Call once per process."""
    _require_env()

    system_prompt = build_system_prompt()
    namespaces = _all_namespaces()

    mcp_tools = await _discover_mcp_tools()
    raw_kb_tool = next(t for t in mcp_tools if t.name == "search_knowledge_base")

    min_relevance_score = float(os.environ.get("KB_MIN_RELEVANCE_SCORE", "0.4"))
    tools = [build_search_all_government_knowledge_tool(raw_kb_tool, namespaces, min_relevance_score)]
    logger.info("Bound %d tool(s) to the agent: %s", len(tools), [t.name for t in tools])

    llm = ChatOpenAI(
        model=os.environ.get("LLM_MODEL_NAME", "gpt-4o"),
        temperature=float(os.environ.get("MODEL_TEMPERATURE", "0.1")),
        max_tokens=int(os.environ.get("MAX_TOKENS", "1000")),
        api_key=os.environ["OPENAI_API_KEY"],
    ).bind_tools(tools)

    async def call_model(state: CentralPortalState):
        language = state.get("language", "en")
        # The language directive goes first and is repeated as its own message
        # (rather than appended after the persona prompt) because a single
        # trailing system message is too easy for the model to deprioritize
        # against the much longer persona/grounding instructions that follow.
        messages = [
            SystemMessage(content=_language_instruction(language)),
            SystemMessage(content=system_prompt),
        ] + state["messages"]
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    graph = StateGraph(CentralPortalState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
