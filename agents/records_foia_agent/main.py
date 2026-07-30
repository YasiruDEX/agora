"""FastAPI entry point for the Records / FOIA Agent.

Exposes POST /chat, satisfying the WSO2 Agent Manager deployment runtime contract:
  Request:  {"message": "string", "session_id": "string", "context": {}}
  Response: {"response": "string"}
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent.parent

# Shared infra secrets (PINECONE_*, OPENAI_API_KEY) live in the root .env.
# Agent-specific department config lives in this agent's own .env and
# overrides anything (accidentally) duplicated at the root.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(AGENT_DIR / ".env", override=True)

try:
    from agents.records_foia_agent.graph import build_graph  # noqa: E402
except ModuleNotFoundError:
    from graph import build_graph  # type: ignore[no-redef]  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("records_foia_agent")

PORT = int(os.environ.get("PORT", "8006"))


class ChatRequest(BaseModel):
    message: str
    session_id: str
    context: Optional[dict[str, Any]] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    response: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Building LangGraph runnable (LLM + Pinecone MCP + Records DB MCP + A2A tool)...")
    app.state.graph = await build_graph()
    logger.info("Records / FOIA Agent ready.")
    yield


app = FastAPI(title="Records / FOIA Agent", lifespan=lifespan)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    logger.info(
        "Received chat request: session_id=%s message=%r context=%s",
        request.session_id,
        request.message,
        request.context,
    )

    graph = app.state.graph
    config = {"configurable": {"thread_id": request.session_id}}
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=request.message)],
            "session_id": request.session_id,
        },
        config=config,
    )

    final_message = result["messages"][-1]
    response_text = final_message.content if isinstance(final_message, AIMessage) else str(final_message.content)

    logger.info("Responding to session_id=%s with: %r", request.session_id, response_text)
    return ChatResponse(response=response_text)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
