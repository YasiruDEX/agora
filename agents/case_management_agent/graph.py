"""LangGraph runnable for the Case Management Agent.

Dynamically discovers tools from two remote MCP servers (pinecone-kb,
case-db-mcp) over SSE, pins the Pinecone tool's namespace to this
department's KB_NAMESPACE, and enforces On-Behalf-Of (OBO) caseworker
scoping: the raw case-db-mcp CRUD tools are NEVER bound directly to the LLM.
Instead they are wrapped into ownership-checked tools (get_my_cases /
get_case_notes / add_case_note / update_case_status) that hard-enforce
`assigned_caseworker == user_id` at the tool layer — a caseworker cannot see
or modify another caseworker's case no matter how the request is phrased,
because the underlying query is always scoped to their own user_id, pulled
from graph state via InjectedState (never exposed to the LLM's tool-call
schema).

This agent container does not run the MCP servers itself — it only holds
their network addresses (PINECONE_MCP_URL, CASE_DB_MCP_URL), configured via
environment variables. The MCP servers and their databases are deployed and
scaled independently (see mcp_servers/*/server.py, run with MCP_TRANSPORT=sse).
"""
import json
import logging
import os
import string
import uuid
from pathlib import Path
from typing import Annotated, Any, Optional

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool, tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import InjectedState, ToolNode, tools_condition
from pydantic import BaseModel, Field

from langchain_mcp_adapters.client import MultiServerMCPClient

# This absolute import only resolves when the full monorepo layout is present
# (agents/ as an importable package alongside mcp_servers/, data/, etc). Some
# deployment platforms instead package this agent's own directory in
# isolation as the process's working directory — in that case `agents` never
# exists, but `tools.py` sits right next to this file and imports directly.
try:
    from agents.case_management_agent.tools import consult_citizen_inquiry_agent
except ModuleNotFoundError:
    from tools import consult_citizen_inquiry_agent  # type: ignore[no-redef]

logger = logging.getLogger("case_management_agent.graph")

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
CASE_DB_MCP_URL = os.environ.get("CASE_DB_MCP_URL", "http://localhost:9003/sse")

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


class CaseAgentState(MessagesState):
    """Extends MessagesState with session_id and user_id (OBO identity)."""

    session_id: str
    user_id: str


def _require_env() -> None:
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


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
    query: str = Field(description="Natural language question to search for.")
    top_k: int = Field(default=5, description="Number of matching chunks to return.")


async def _discover_mcp_tools() -> list:
    """Connect to both MCP servers and dynamically discover their tools."""
    client = MultiServerMCPClient(
        {
            "pinecone-kb": {
                "url": PINECONE_MCP_URL,
                "transport": "sse",
            },
            "case-db-mcp": {
                "url": CASE_DB_MCP_URL,
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
            "Use this to ground next-step suggestions in actual eligibility/procedure rules."
        ),
        args_schema=SearchKnowledgeBaseArgs,
    )


def _extract_text(result: Any) -> str:
    """Normalize an MCP tool's ainvoke() result to plain text.

    langchain-mcp-adapters returns a list of MCP content blocks (e.g.
    [{"type": "text", "text": "..."}]) rather than a plain string, so this
    result cannot be passed directly to str methods like .startswith() or
    json.loads() without first pulling the text out.
    """
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        return "".join(
            block.get("text", "") for block in result if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(result)


def _build_obo_case_tools(raw_read_tool, raw_create_tool, raw_update_tool) -> list:
    """Build ownership-checked case tools, closing over the raw case-db-mcp tools.

    None of these ever expose `user_id`, `table_name`, or raw SQL-shaped
    parameters to the LLM — every call is scoped to the caseworker identified
    by the current graph state's `user_id` (via InjectedState), and every
    write/read is checked against that caseworker's own assigned cases before
    the underlying raw tool is ever invoked.
    """

    async def _fetch_case(case_id: str) -> Optional[dict[str, Any]]:
        raw_result = await raw_read_tool.ainvoke({"table_name": "cases", "query_params": {"case_id": case_id}})
        result = _extract_text(raw_result)
        if result.startswith("No rows found"):
            return None
        rows = json.loads(result)
        return rows[0] if rows else None

    def _denied(user_id: str, case_id: str, owner: str) -> str:
        logger.warning("OBO DENIED: user_id=%s attempted to access case_id=%s (owned by %s)", user_id, case_id, owner)
        return (
            f"ACCESS DENIED: case '{case_id}' is not assigned to you. "
            "You may only view or modify cases assigned to your own caseload."
        )

    @tool
    async def get_my_cases(state: Annotated[dict, InjectedState]) -> str:
        """List all cases assigned to the current caseworker."""
        user_id = state.get("user_id", "unknown-user")
        raw_result = await raw_read_tool.ainvoke({"table_name": "cases", "query_params": {"assigned_caseworker": user_id}})
        return _extract_text(raw_result)

    @tool
    async def get_case_notes(case_id: str, state: Annotated[dict, InjectedState]) -> str:
        """Get a case's details and notes, only if it is assigned to the current caseworker.

        Args:
            case_id: The case ID to look up, e.g. 'CASE-2026-001'.
        """
        user_id = state.get("user_id", "unknown-user")
        case = await _fetch_case(case_id)
        if case is None:
            return f"No case found with ID '{case_id}'."
        if case["assigned_caseworker"] != user_id:
            return _denied(user_id, case_id, case["assigned_caseworker"])
        raw_notes = await raw_read_tool.ainvoke({"table_name": "case_notes", "query_params": {"case_id": case_id}})
        notes = _extract_text(raw_notes)
        return f"Case: {json.dumps(case, default=str)}\nNotes: {notes}"

    @tool
    async def add_case_note(case_id: str, note_text: str, state: Annotated[dict, InjectedState]) -> str:
        """Add a new note to a case, only if it is assigned to the current caseworker.

        Args:
            case_id: The case ID to add a note to, e.g. 'CASE-2026-001'.
            note_text: The note content to record.
        """
        user_id = state.get("user_id", "unknown-user")
        case = await _fetch_case(case_id)
        if case is None:
            return f"No case found with ID '{case_id}'."
        if case["assigned_caseworker"] != user_id:
            return _denied(user_id, case_id, case["assigned_caseworker"])
        note_id = f"NOTE-{case_id}-{uuid.uuid4().hex[:8]}"
        raw_result = await raw_create_tool.ainvoke(
            {
                "table_name": "case_notes",
                "record_data": {"note_id": note_id, "case_id": case_id, "author_id": user_id, "note_text": note_text},
            }
        )
        return _extract_text(raw_result)

    @tool
    async def update_case_status(case_id: str, new_status: str, state: Annotated[dict, InjectedState]) -> str:
        """Update a case's status, only if it is assigned to the current caseworker.

        Args:
            case_id: The case ID to update, e.g. 'CASE-2026-001'.
            new_status: The new status, e.g. 'PENDING_REVIEW', 'OPEN', 'CLOSED'.
        """
        user_id = state.get("user_id", "unknown-user")
        case = await _fetch_case(case_id)
        if case is None:
            return f"No case found with ID '{case_id}'."
        if case["assigned_caseworker"] != user_id:
            return _denied(user_id, case_id, case["assigned_caseworker"])
        raw_result = await raw_update_tool.ainvoke(
            {"table_name": "cases", "key_field": "case_id", "key_value": case_id, "update_data": {"status": new_status}}
        )
        return _extract_text(raw_result)

    return [get_my_cases, get_case_notes, add_case_note, update_case_status]


async def build_graph():
    """Build and compile the LangGraph runnable. Call once per process."""
    _require_env()

    system_prompt = build_system_prompt()
    namespace = os.environ["KB_NAMESPACE"]

    mcp_tools = await _discover_mcp_tools()
    kb_tool = next(t for t in mcp_tools if t.name == "search_knowledge_base")
    raw_read_tool = next(t for t in mcp_tools if t.name == "db_read_record")
    raw_create_tool = next(t for t in mcp_tools if t.name == "db_create_record")
    raw_update_tool = next(t for t in mcp_tools if t.name == "db_update_record")

    tools = [
        _wrap_kb_tool_with_pinned_namespace(kb_tool, namespace),
        *_build_obo_case_tools(raw_read_tool, raw_create_tool, raw_update_tool),
        consult_citizen_inquiry_agent,
    ]
    logger.info("Bound %d tool(s) to the agent: %s", len(tools), [t.name for t in tools])

    llm_kwargs: dict[str, Any] = dict(
        model=os.environ.get("LLM_MODEL_NAME", "gpt-4o"),
        temperature=float(os.environ.get("MODEL_TEMPERATURE", "0.1")),
        max_tokens=int(os.environ.get("MAX_TOKENS", "1000")),
        api_key=os.environ["OPENAI_API_KEY"],
    )
    # LLM_PROVIDER_KEY="onprem-vllm" declares the governance intent (case data
    # is sensitive citizen PII); LLM_BASE_URL is how that's actually wired to a
    # real on-prem OpenAI-compatible vLLM endpoint. Unset, this falls back to
    # the public OpenAI API.
    base_url = os.environ.get("LLM_BASE_URL")
    if base_url:
        llm_kwargs["base_url"] = base_url

    llm = ChatOpenAI(**llm_kwargs).bind_tools(tools)

    async def call_model(state: CaseAgentState):
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    graph = StateGraph(CaseAgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
