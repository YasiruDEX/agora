"""Agent-to-agent communication: forward out-of-scope questions to the Citizen Inquiry Agent.

Uses LangGraph's InjectedState mechanism so `session_id` is pulled from the
running graph's state at call time, without ever being exposed to the LLM's
tool-call schema.
"""
import os
from typing import Annotated

import httpx
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

DEFAULT_INQUIRY_AGENT_URL = "http://localhost:8001/chat"
REQUEST_TIMEOUT_SECONDS = 30.0


@tool
async def consult_citizen_inquiry_agent(user_query: str, state: Annotated[dict, InjectedState]) -> str:
    """Forward a general municipal question to the Citizen Inquiry Agent.

    Use this when the caseworker or citizen asks something OUTSIDE case
    management (e.g. permits, tax payments, health and environmental matters).

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
