"""Agent-to-agent forwarding and MCP-result helpers for the Records/FOIA Agent."""
import os
from typing import Annotated, Any

import httpx
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

DEFAULT_INQUIRY_AGENT_URL = "http://localhost:8001/chat"
REQUEST_TIMEOUT_SECONDS = 30.0


@tool
async def consult_citizen_inquiry_agent(user_query: str, state: Annotated[dict, InjectedState]) -> str:
    """Forward a general municipal question to the Citizen Inquiry Agent.

    Use this when the requester asks something OUTSIDE public records / FOIA
    (e.g. permits, tax payments, welfare benefits).

    Args:
        user_query: The out-of-scope question, forwarded as-is.
    """
    session_id = state.get("session_id", "unknown-session")
    url = os.environ.get("INQUIRY_AGENT_URL", DEFAULT_INQUIRY_AGENT_URL)

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                url,
                json={"message": user_query, "session_id": session_id, "context": {}},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")
    except httpx.HTTPError as e:
        return (
            "I couldn't reach the general Citizen Inquiry service right now "
            f"({e}). Please try again shortly or contact the relevant department directly."
        )


def extract_text(result: Any) -> str:
    """Normalize an MCP tool's ainvoke() result to plain text.

    langchain-mcp-adapters returns a list of MCP content blocks (e.g.
    [{"type": "text", "text": "..."}]) rather than a plain string, so callers
    cannot use str methods (.startswith(), json.loads()) on it directly
    without first pulling the text out.
    """
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        return "".join(
            block.get("text", "") for block in result if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(result)


async def apply_redaction(raw_redact_tool, text: str) -> str:
    """Call the redact_pii_text MCP tool and normalize its output to plain text."""
    raw_result = await raw_redact_tool.ainvoke({"text": text})
    return extract_text(raw_result)
