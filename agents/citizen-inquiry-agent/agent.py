"""LangGraph Citizen Inquiry Agent construction.

Builds a ReAct-style agent bound to whichever KB tools this instance's API key resolved to.
When ``USE_LLM_PROVIDER=true``, requests are routed through the AM LLM provider (which
applies guardrails); otherwise calls OpenAI directly.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import Config

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT_TEMPLATE = (
    "You are the Citizen Inquiry Agent for {county_name}'s {department_name} department. "
    "You answer resident questions using the department's knowledge base and nothing else.\n\n"
    "CAPABILITIES:\n"
    "- kb_search: find relevant KB articles for a resident's question\n"
    "- kb_read: fetch the full text of a specific article by its doc_id\n"
    "- kb_list_sources: list what topics/articles exist in this department's KB\n"
    "- kb_write: file a new or updated KB note (use sparingly, e.g. to log a follow-up)\n\n"
    "RULES YOU MUST FOLLOW:\n"
    "1. GROUNDING: Always search the knowledge base before answering a substantive question. "
    "Base your answer only on what kb_search/kb_read return — never invent policy details, "
    "fees, deadlines, or eligibility rules.\n"
    "2. SCOPE: You only have access to {department_name}'s knowledge base. If a resident asks "
    "about a different department's services (e.g. asking Tax & Revenue about a building "
    "permit), say so plainly and suggest they contact that department — do not guess.\n"
    "3. CITE: When you give a specific figure, deadline, or rule, mention which article it "
    "came from (by source title) so the answer is traceable.\n"
    "4. NO SPECULATION: If the knowledge base has no relevant article, say you don't have "
    "that information rather than guessing.\n\n"
    "Tone: {tone}. {additional_guidance}"
)


def build_agent(cfg: Config, tools: list[BaseTool]) -> Any:
    if cfg.use_llm_provider:
        llm = ChatOpenAI(
            model=MODEL,
            temperature=0,
            base_url=cfg.llm_provider_url,
            api_key="not-used",
            default_headers={
                "API-Key": cfg.llm_provider_key,
                "Authorization": "",
            },
        )
    else:
        llm = ChatOpenAI(model=MODEL, temperature=0)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        county_name=cfg.county_name,
        department_name=cfg.department_name,
        tone=cfg.tone,
        additional_guidance=cfg.additional_guidance,
    )
    return create_react_agent(model=llm, tools=tools, prompt=system_prompt)
