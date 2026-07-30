"""LangGraph runnable for the Records / FOIA Agent.

Dynamically discovers tools from two MCP servers (pinecone-kb, records-db-mcp),
pins the Pinecone tool's namespace to this department's KB_NAMESPACE, and
enforces the statutory exemption + PII redaction pipeline: the raw
records-db-mcp tools are NEVER bound directly to the LLM. Instead they are
wrapped into `get_public_record`, which checks `is_exempt` BEFORE ever
touching `raw_content` — an exempt record's content is never fetched or
redacted, only its exemption reason is returned. A non-exempt record's content
is always passed through `redact_pii_text` before the LLM ever sees it.
"""
import json
import logging
import os
import string
import sys
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool, tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel, Field

from langchain_mcp_adapters.client import MultiServerMCPClient

from agents.records_foia_agent.tools import apply_redaction, consult_citizen_inquiry_agent, extract_text

logger = logging.getLogger("records_foia_agent.graph")

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent.parent
PROMPT_PATH = AGENT_DIR / "prompt.md"
PINECONE_MCP_SERVER_PATH = REPO_ROOT / "mcp_servers" / "pinecone_kb_mcp" / "server.py"
RECORDS_DB_MCP_SERVER_PATH = REPO_ROOT / "mcp_servers" / "records_db_mcp" / "server.py"

# Shared infra secrets (PINECONE_*, OPENAI_API_KEY) live in the root .env.
# Agent-specific department config lives in this agent's own .env and takes
# precedence over anything (accidentally) duplicated at the root.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(AGENT_DIR / ".env", override=True)

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


class RecordsAgentState(MessagesState):
    """Extends MessagesState with session_id."""

    session_id: str


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
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(PINECONE_MCP_SERVER_PATH)],
                "env": dict(os.environ),
            },
            "records-db-mcp": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(RECORDS_DB_MCP_SERVER_PATH)],
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
        raw_result = await raw_tool.ainvoke({"namespace": namespace, "query": query, "top_k": top_k})
        return extract_text(raw_result)

    return StructuredTool.from_function(
        coroutine=_search,
        name="search_knowledge_base",
        description=(
            f"Semantic search over the '{namespace}' department policy knowledge base. "
            "Use this for FOIA process, exemption category, and response timeline questions."
        ),
        args_schema=SearchKnowledgeBaseArgs,
    )


def _build_records_tools(raw_read_tool, raw_create_tool, raw_update_tool, raw_redact_tool) -> list:
    """Build the exemption-checked, redaction-enforced record tools.

    `get_public_record` NEVER returns `raw_content` unredacted, and NEVER
    returns any content at all for an exempt record — only its
    `exemption_reason`. This is enforced here structurally, not left to the
    LLM's judgment.
    """

    @tool
    async def get_public_record(record_id: str) -> str:
        """Retrieve a public record by ID, applying statutory exemption checks and PII redaction.

        If the record is marked exempt, only an exemption notice (with the
        statutory reason) is returned — its content is never released. If it
        is not exempt, its content is scrubbed of PII (SSNs, phone numbers,
        emails) before being returned.

        Args:
            record_id: The public record ID to retrieve, e.g. 'REC-2026-101'.
        """
        raw_result = await raw_read_tool.ainvoke({"table_name": "public_records", "query_params": {"record_id": record_id}})
        text = extract_text(raw_result)
        if text.startswith("No rows found"):
            return f"No public record found with ID '{record_id}'."

        record = json.loads(text)[0]
        if record.get("is_exempt"):
            reason = record.get("exemption_reason") or "Reason not specified."
            return (
                f"EXEMPTION NOTICE: Record '{record_id}' (\"{record['title']}\") is exempt from disclosure "
                f"under Sri Lanka's Right to Information framework.\n"
                f"Exemption reason: {reason}\n"
                "The underlying content of this record cannot be released."
            )

        redacted_content = await apply_redaction(raw_redact_tool, record["raw_content"])
        return (
            f"Record '{record_id}': {record['title']} (Category: {record['category']})\n\n"
            f"{redacted_content}"
        )

    @tool
    async def submit_foia_request(requester_name: str, requester_email: str, requested_category: str) -> str:
        """Log a new public records (FOIA/RTI) request intake.

        Args:
            requester_name: Full name of the person making the request.
            requester_email: Contact email of the requester.
            requested_category: Record category being requested, e.g. 'MUNICIPAL_CONTRACT'.
        """
        request_id = f"FOIA-{uuid.uuid4().hex[:8].upper()}"
        raw_result = await raw_create_tool.ainvoke(
            {
                "table_name": "foia_requests",
                "record_data": {
                    "request_id": request_id,
                    "requester_name": requester_name,
                    "requester_email": requester_email,
                    "requested_category": requested_category,
                    "status": "RECEIVED",
                },
            }
        )
        result = extract_text(raw_result)
        return f"{result} Request ID: {request_id} (status: RECEIVED)."

    @tool
    async def update_foia_request_status(request_id: str, status: str, released_content: str = "") -> str:
        """Update a FOIA/RTI request's status once it has been actioned.

        Args:
            request_id: The FOIA request ID to update, e.g. 'FOIA-AB12CD34'.
            status: New status, e.g. 'FULFILLED' or 'DENIED_EXEMPT'.
            released_content: The redacted content actually released, if fulfilled.
        """
        update_data: dict[str, Any] = {"status": status}
        if released_content:
            update_data["released_content"] = released_content
        raw_result = await raw_update_tool.ainvoke(
            {"table_name": "foia_requests", "key_field": "request_id", "key_value": request_id, "update_data": update_data}
        )
        return extract_text(raw_result)

    return [get_public_record, submit_foia_request, update_foia_request_status]


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
    raw_redact_tool = next(t for t in mcp_tools if t.name == "redact_pii_text")

    tools = [
        _wrap_kb_tool_with_pinned_namespace(kb_tool, namespace),
        *_build_records_tools(raw_read_tool, raw_create_tool, raw_update_tool, raw_redact_tool),
        consult_citizen_inquiry_agent,
    ]
    logger.info("Bound %d tool(s) to the agent: %s", len(tools), [t.name for t in tools])

    llm = ChatOpenAI(
        model=os.environ.get("LLM_MODEL_NAME", "gpt-4o"),
        temperature=float(os.environ.get("MODEL_TEMPERATURE", "0.1")),
        max_tokens=int(os.environ.get("MAX_TOKENS", "1000")),
        api_key=os.environ["OPENAI_API_KEY"],
    ).bind_tools(tools)

    async def call_model(state: RecordsAgentState):
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = await llm.ainvoke(messages)
        return {"messages": [response]}

    graph = StateGraph(RecordsAgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
