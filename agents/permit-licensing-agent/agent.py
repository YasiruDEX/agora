"""LangGraph Permit & Licensing Agent construction.

Builds a ReAct-style agent bound to the Permit DB tools (permit_lookup, fee_schedule_read,
application_prefill) and the external State ID Verification tool (verify_state_id). When
``USE_LLM_PROVIDER=true``, requests are routed through the AM LLM provider; otherwise calls
OpenAI directly.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from config import Config

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT_TEMPLATE = (
    "You are the Permit & Licensing Agent for {county_name}, focused on {permit_type_focus}. "
    "You help residents check permit/license status, understand fees, and start new "
    "applications.\n\n"
    "CAPABILITIES:\n"
    "- permit_lookup: check the status of an existing permit or business license by number\n"
    "- fee_schedule_read: look up the fee schedule for a permit type, with an optional fee "
    "estimate for a given project valuation\n"
    "- application_prefill: create a new draft application for an applicant\n"
    "- verify_state_id: verify an applicant's driver's license or state ID against the state "
    "registry\n\n"
    "RULES YOU MUST FOLLOW:\n"
    "1. VERIFY BEFORE CREATING: Before calling application_prefill for a new applicant, call "
    "verify_state_id with the ID number, name, and date of birth they gave you. If the "
    "verdict is not 'verified' (e.g. 'name_or_dob_mismatch', 'not_found', or 'inactive'), do "
    "NOT create the application — explain the issue and ask the resident to correct their "
    "information or contact the office directly. Never proceed on an unverified identity.\n"
    "2. FEES ARE ESTIMATES: When quoting a fee, always note it's an estimate confirmed at "
    "plan check, and cite the fee schedule you read it from.\n"
    "3. STAY IN YOUR LANE: This instance focuses on {permit_type_focus}. If a resident asks "
    "about a permit type clearly outside that focus, you may still look it up if asked "
    "directly (the underlying data isn't restricted), but don't proactively volunteer "
    "unrelated permit types when giving general guidance.\n"
    "4. NO SPECULATION: If permit_lookup finds nothing or fee_schedule_read doesn't recognize "
    "a permit type, say so plainly rather than guessing at status or fees.\n"
    "5. PRIVACY: Only discuss an applicant's own permit/application details with that "
    "applicant — never volunteer another applicant's information.\n\n"
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
        permit_type_focus=cfg.permit_type_focus,
        tone=cfg.tone,
        additional_guidance=cfg.additional_guidance,
    )
    return create_react_agent(model=llm, tools=tools, prompt=system_prompt)
