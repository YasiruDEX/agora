"""FastAPI entry point for the Central Portal Chat Agent.

Exposes POST /chat, satisfying the WSO2 Agent Manager deployment runtime contract
plus this agent's cross-namespace metadata and language extensions:
  Request:  {"message": "string", "session_id": "string", "language": "en"|"si"|"ta", "context": {}}
  Response: {"response": "string", "contributing_namespaces": ["..."]}
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent.parent

# Shared infra secrets (OPENAI_API_KEY) live in the root .env.
# Agent-specific config lives in this agent's own .env and overrides anything
# (accidentally) duplicated at the root.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(AGENT_DIR / ".env", override=True)

try:
    from agents.central_portal_agent.graph import build_graph  # noqa: E402
    from agents.central_portal_agent.tools import NAMESPACE_TAG_RE  # noqa: E402
except ModuleNotFoundError:
    from graph import build_graph  # type: ignore[no-redef]  # noqa: E402
    from tools import NAMESPACE_TAG_RE  # type: ignore[no-redef]  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("central_portal_agent")

PORT = int(os.environ.get("PORT", "8007"))


class ChatRequest(BaseModel):
    message: str
    session_id: str
    language: Optional[str] = "en"
    context: Optional[dict[str, Any]] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    response: str
    contributing_namespaces: list[str] = Field(default_factory=list)


def _contributing_namespaces(messages: list) -> list[str]:
    """Recover which department namespace(s) contributed to THIS turn's answer
    by scanning the tool messages produced since the last HumanMessage --
    search_all_government_knowledge tags each result block with
    `namespace=...` (see tools.py); we just collect the distinct set. Scoping
    to "since the last HumanMessage" (rather than the whole checkpointed
    history) matters because MemorySaver keeps every prior turn's messages
    around too.
    """
    last_human_idx = max(
        (i for i, m in enumerate(messages) if isinstance(m, HumanMessage)),
        default=-1,
    )
    namespaces: set[str] = set()
    for m in messages[last_human_idx + 1 :]:
        if isinstance(m, ToolMessage) and m.name == "search_all_government_knowledge":
            namespaces.update(NAMESPACE_TAG_RE.findall(m.content if isinstance(m.content, str) else str(m.content)))
    return sorted(namespaces)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Building LangGraph runnable (LLM + multi-namespace local KB MCP tool)...")
    app.state.graph = await build_graph()
    logger.info("Central Portal Chat Agent ready on port %d.", PORT)
    yield


app = FastAPI(title="Central Portal Chat Agent", lifespan=lifespan)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    logger.info(
        "Received chat request: session_id=%s language=%s message=%r context=%s",
        request.session_id,
        request.language,
        request.message,
        request.context,
    )

    graph = app.state.graph
    config = {"configurable": {"thread_id": request.session_id}}
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=request.message)],
            "language": request.language or "en",
        },
        config=config,
    )

    final_message = result["messages"][-1]
    response_text = final_message.content if isinstance(final_message, AIMessage) else str(final_message.content)
    contributing_namespaces = _contributing_namespaces(result["messages"])

    logger.info(
        "Responding to session_id=%s (namespaces=%s) with: %r",
        request.session_id,
        contributing_namespaces,
        response_text,
    )
    return ChatResponse(response=response_text, contributing_namespaces=contributing_namespaces)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
