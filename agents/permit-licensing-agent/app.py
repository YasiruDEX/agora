"""FastAPI entrypoint for the Permit & Licensing Agent.

Implements the AM chat-agent contract: ``POST /chat`` on port 8000 accepting
``{session_id, message, context}`` and returning ``{response, session_id}``.
``GET /health`` is provided for local checks (AM does not require it).

MCP tools are (re)loaded on every ``/chat`` request, authenticating via OAuth2 AgentID tokens
(see mcp_tools.py) — which department/resource each token resolves to is entirely up to the
MCP server/proxy, not this agent. Building the tool set once at startup and reusing it forever
would mean every request after a token's short TTL expires fails deep inside the MCP client's
connection setup instead of getting a fresh token — see mcp_tools.py's docstring.
``load_permit_tools`` caches each token itself and only re-fetches once it's actually close to
expiry, so this isn't a token-endpoint call on every message, just a cheap rebuild of the tool
wrappers.

Tool calls to an MCP proxy have also been observed to fail intermittently with a raw HTTP
403/503 from the gateway itself (not a clean MCP protocol error from the backend server) —
e.g. a tool call this agent's identity has no scope for gets rejected by the platform before
it ever reaches the MCP server. Because that failure happens inside the MCP client's
transport-level connection setup (an anyio TaskGroup) or the session's async-context teardown,
it bypasses LangGraph's normal per-tool error handling entirely and surfaces as an opaque
``ExceptionGroup: unhandled errors in a TaskGroup``. ``chat()`` below retries the whole agent
invocation a couple of times first, since some of these are transient — but if it's still
failing after retries (e.g. a genuine scope denial a retry can't fix), the resident still gets
a normal, in-character response instead of an HTTP 500. The real exception is always logged
server-side either way.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import FastAPI
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from agent import build_agent
from config import Config
from mcp_tools import load_permit_tools

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 1.0

# Shown to the resident when every retry still failed at the transport level. Deliberately
# generic — the real exception (which may include internal URLs) only ever goes to the server
# log, never to the end user.
_TOOL_ACCESS_UNAVAILABLE_MESSAGE = (
    "I'm sorry, I don't have access to that right now — one of my tools was denied by the "
    "platform. This isn't something you did wrong; please try again in a moment, or contact "
    "the department directly if it keeps happening."
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("permit-licensing-agent")

CONFIG = Config.from_env()
log.info(
    "Permit & Licensing Agent starting (focus=%s, permitdb=%s, stateid=%s, llm_provider=%s)",
    CONFIG.permit_type_focus,
    CONFIG.permitdb_mcp_server_url,
    CONFIG.stateid_mcp_server_url,
    "agent-manager" if CONFIG.use_llm_provider else "openai-direct",
)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    context: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str | None = None


app = FastAPI(title="Permit & Licensing Agent", version="0.1.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "county": CONFIG.county_name, "focus": CONFIG.permit_type_focus}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    result = None
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            tools = await load_permit_tools(CONFIG)
            agent = build_agent(CONFIG, tools)
            result = await agent.ainvoke({"messages": [HumanMessage(content=req.message)]})
            last_exc = None
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < _MAX_ATTEMPTS:
                log.warning(
                    "agent invocation failed (attempt %d/%d), retrying: %s",
                    attempt,
                    _MAX_ATTEMPTS,
                    exc,
                )
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)

    if last_exc is not None:
        log.exception("agent invocation failed after %d attempts", _MAX_ATTEMPTS, exc_info=last_exc)
        return ChatResponse(response=_TOOL_ACCESS_UNAVAILABLE_MESSAGE, session_id=req.session_id)

    final: Any = None
    for m in reversed(result.get("messages", [])):
        if isinstance(m, AIMessage):
            final = m.content
            break
    if final is None:
        final = "(no response)"
    if isinstance(final, list):
        final = "\n".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in final
        )
    return ChatResponse(response=str(final), session_id=req.session_id)
