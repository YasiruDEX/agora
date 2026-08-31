"""FastAPI entrypoint for the Citizen Inquiry Agent.

Implements the AM chat-agent contract: ``POST /chat`` on port 8000 accepting
``{session_id, message, context}`` and returning ``{response, session_id}``.
``GET /health`` is provided for local checks (AM does not require it).

MCP tools are (re)loaded on every ``/chat`` request, authenticating via an OAuth2 AgentID
token (see mcp_tools.py) — which department namespace that resolves to is entirely up to the
MCP server/proxy, not this agent. Building the tool set once at startup and reusing it forever
would mean every request after the access token's short TTL expires fails deep inside the MCP
client's connection setup instead of getting a fresh token — see mcp_tools.py's docstring.
``load_kb_tools`` caches the token itself and only re-fetches once it's actually close to
expiry, so this isn't a token-endpoint call on every message, just a cheap rebuild of the tool
wrappers.

Tool calls to the MCP proxy have also been observed to fail intermittently with a raw HTTP
403/503 from the gateway itself (not a clean MCP protocol error from the KB server) — e.g. a
tool call the agent's identity has no scope for gets rejected by the platform before it ever
reaches the MCP server. Because that failure happens inside the MCP client's transport-level
connection setup (an anyio TaskGroup) or the session's async-context teardown, it bypasses
LangGraph's normal per-tool error handling entirely (which expects a clean tool-level
exception, not a transport failure raised while a context manager is exiting) and surfaces as
an opaque ``ExceptionGroup: unhandled errors in a TaskGroup``. ``chat()`` below retries the
whole agent invocation a couple of times first, since some of these are transient (see
mcp_tools.py's docstring) — but if it's still failing after retries (e.g. a genuine scope
denial that a retry can't fix), the resident still gets a normal, in-character response
instead of an HTTP 500: something like "I don't have access to that right now." The real
exception is always logged server-side either way.
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
from mcp_tools import load_kb_tools

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 1.0

# Shown to the resident when every retry still failed at the transport level (e.g. a genuine
# tool-scope denial from the platform, not something a retry can fix). Deliberately generic —
# the real exception (which may include internal URLs) only ever goes to the server log, never
# to the end user.
_TOOL_ACCESS_UNAVAILABLE_MESSAGE = (
    "I'm sorry, I don't have access to that right now — one of my tools was denied by the "
    "platform. This isn't something you did wrong; please try again in a moment, or contact "
    "the department directly if it keeps happening."
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("citizen-inquiry-agent")

CONFIG = Config.from_env()
log.info(
    "Citizen Inquiry Agent starting (department=%s, mcp_server=%s, llm_provider=%s)",
    CONFIG.department_name,
    CONFIG.mcp_server_url,
    "agent-manager" if CONFIG.use_llm_provider else "openai-direct",
)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    context: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str | None = None


app = FastAPI(title="Citizen Inquiry Agent", version="0.1.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "county": CONFIG.county_name, "department": CONFIG.department_name}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    result = None
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            tools = await load_kb_tools(CONFIG)
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
