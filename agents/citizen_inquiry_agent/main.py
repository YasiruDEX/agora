"""FastAPI entry point for the Citizen Inquiry Agent.

Exposes POST /chat, satisfying the WSO2 Agent Manager deployment runtime contract:
  Request:  {"message": "string", "session_id": "string", "context": {}}
  Response: {"response": "string"}
"""
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from agents.citizen_inquiry_agent.graph import build_graph

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("citizen_inquiry_agent")


class ChatRequest(BaseModel):
    message: str
    session_id: str
    context: Optional[dict[str, Any]] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    response: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Building LangGraph runnable (LLM + Pinecone MCP tool)...")
    app.state.graph = await build_graph()
    logger.info("Citizen Inquiry Agent ready.")
    yield


app = FastAPI(title="Citizen Inquiry Agent", lifespan=lifespan)


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
    result = await graph.ainvoke({"messages": [HumanMessage(content=request.message)]}, config=config)

    final_message = result["messages"][-1]
    response_text = final_message.content if isinstance(final_message, AIMessage) else str(final_message.content)

    logger.info("Responding to session_id=%s with: %r", request.session_id, response_text)
    return ChatResponse(response=response_text)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("agents.citizen_inquiry_agent.main:app", host="0.0.0.0", port=8000)
