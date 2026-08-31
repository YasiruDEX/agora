"""FastAPI entrypoint for the Citizen Inquiry Agent.

Implements the AM chat-agent contract: ``POST /chat`` on port 8000 accepting
``{session_id, message, context}`` and returning ``{response, session_id}``.
``GET /health`` is provided for local checks (AM does not require it).

MCP tools are loaded once at startup against this instance's MCP_SERVER_URL, authenticating
via an OAuth2 AgentID token (see mcp_tools.py) — which department namespace that resolves to
is entirely up to the MCP server/proxy, not this agent.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
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
AGENT: Any = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global AGENT
    tools = await load_kb_tools(CONFIG)
    tool_names = [t.name for t in tools]
    AGENT = build_agent(CONFIG, tools)
    log.info(
        "Citizen Inquiry Agent ready (department=%s, mcp_server=%s, tools=%s, llm_provider=%s)",
        CONFIG.department_name,
        CONFIG.mcp_server_url,
        tool_names,
        "agent-manager" if CONFIG.use_llm_provider else "openai-direct",
    )
    yield


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    context: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str | None = None


app = FastAPI(title="Citizen Inquiry Agent", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "county": CONFIG.county_name, "department": CONFIG.department_name}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if AGENT is None:
        raise HTTPException(status_code=503, detail="Agent is still starting up")
    try:
        result = await AGENT.ainvoke({"messages": [HumanMessage(content=req.message)]})
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
