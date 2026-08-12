"""FastAPI entrypoint for the Permit & Licensing Agent.

Implements the AM chat-agent contract: ``POST /chat`` on port 8000 accepting
``{session_id, message, context}`` and returning ``{response, session_id}``.
``GET /health`` is provided for local checks (AM does not require it).
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
from mcp_tools import load_permit_tools

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("permit-licensing-agent")

CONFIG = Config.from_env()
AGENT: Any = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global AGENT
    tools = await load_permit_tools(CONFIG)
    tool_names = [t.name for t in tools]
    AGENT = build_agent(CONFIG, tools)
    log.info(
        "Permit & Licensing Agent ready (focus=%s, permitdb=%s, stateid=%s, tools=%s, llm_provider=%s)",
        CONFIG.permit_type_focus,
        CONFIG.permitdb_mcp_server_url,
        CONFIG.stateid_mcp_server_url,
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


app = FastAPI(title="Permit & Licensing Agent", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "county": CONFIG.county_name, "focus": CONFIG.permit_type_focus}


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
