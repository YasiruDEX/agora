"""Agent-to-agent communication: forward out-of-scope questions to the Citizen Inquiry Agent."""
import os

import httpx

DEFAULT_INQUIRY_AGENT_URL = "http://localhost:8001/chat"
REQUEST_TIMEOUT_SECONDS = 30.0


async def consult_citizen_inquiry_agent(user_query: str, session_id: str) -> str:
    """Forward a general municipal question to the Citizen Inquiry Agent over HTTP.

    Args:
        user_query: The citizen's question, forwarded as-is.
        session_id: Thread/session identifier to pass through so the downstream
            agent can maintain its own conversation state for this citizen.

    Returns:
        The Citizen Inquiry Agent's response text, or an error message if the
        call failed (e.g. the other agent isn't running).
    """
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
