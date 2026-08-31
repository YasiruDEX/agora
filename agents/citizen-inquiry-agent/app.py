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
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from agent import build_agent
from config import Config
from mcp_tools import load_kb_tools

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
    try:
        tools = await load_kb_tools(CONFIG)
        agent = build_agent(CONFIG, tools)
        result = await agent.ainvoke({"messages": [HumanMessage(content=req.message)]})
    except Exception as exc:  # noqa: BLE001
        log.exception("agent invocation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

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
