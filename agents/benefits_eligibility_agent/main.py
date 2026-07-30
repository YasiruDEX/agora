"""FastAPI entry point for the Benefits & Eligibility Agent.

Exposes POST /chat, satisfying the WSO2 Agent Manager deployment runtime contract:
  Request:  {"message": "string", "session_id": "string", "context": {}}
  Response: {"response": "string"}
"""
import logging
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

# This absolute import only resolves when the full monorepo layout is present
# (agents/ as an importable package alongside mcp_servers/, data/, etc). Some
# deployment platforms instead package this agent's own directory in
# isolation as the process's working directory — in that case `agents` never
# exists, but `graph.py` sits right next to this file and imports directly.
try:
    from agents.benefits_eligibility_agent.graph import build_graph  # noqa: E402
except ModuleNotFoundError:
    from graph import build_graph  # type: ignore[no-redef]  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("benefits_eligibility_agent")


class ChatRequest(BaseModel):
    message: str
    session_id: str
    context: Optional[dict[str, Any]] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    response: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Building LangGraph runnable (LLM + Pinecone MCP + SQLite MCP + A2A tool)...")
    app.state.graph = await build_graph()
    logger.info("Benefits & Eligibility Agent ready.")
    yield


app = FastAPI(title="Benefits & Eligibility Agent", lifespan=lifespan)


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
    uvicorn.run("agents.benefits_eligibility_agent.main:app", host="0.0.0.0", port=8000)
