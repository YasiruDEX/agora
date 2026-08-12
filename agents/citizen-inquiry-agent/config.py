"""Instance-level configuration for the Citizen Inquiry Agent, read from env at startup.

One image, one codebase — every one of the 5 department instances (Social Services, Permits
& Licensing, Tax & Revenue, Records & Compliance, Contact Center) is this same agent, told
apart only by the env vars Agent Manager injects at deploy time (PLAN.md §5/§6):
``MCP_SERVER_URL``/``MCP_API_KEY`` point it at the Unified KB MCP server and resolve it to one
department namespace server-side; ``DEPARTMENT_NAME`` only affects tone/branding in the
prompt, never which KB namespace is reachable — that boundary is enforced by the MCP server,
not by this agent trusting its own env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if val is None:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


@dataclass(frozen=True)
class Config:
    county_name: str
    department_name: str
    mcp_server_url: str
    mcp_api_key: str
    tone: str
    additional_guidance: str
    use_llm_provider: bool
    llm_provider_url: str
    llm_provider_key: str
    port: int

    @classmethod
    def from_env(cls) -> "Config":
        use_llm_provider = _env("USE_LLM_PROVIDER", "false").lower() == "true"
        llm_provider_url = _env("LLM_PROVIDER_URL", "")
        llm_provider_key = _env("LLM_PROVIDER_KEY", "")

        if use_llm_provider:
            if not llm_provider_url:
                raise RuntimeError("USE_LLM_PROVIDER is true but LLM_PROVIDER_URL is not set")
            if not llm_provider_key:
                raise RuntimeError("USE_LLM_PROVIDER is true but LLM_PROVIDER_KEY is not set")

        return cls(
            county_name=_env("COUNTY_NAME", "Riverside County"),
            department_name=_env("DEPARTMENT_NAME"),
            mcp_server_url=_env("MCP_SERVER_URL"),
            mcp_api_key=_env("MCP_API_KEY"),
            tone=_env("TONE", "clear, courteous, and plain-language"),
            additional_guidance=_env("ADDITIONAL_GUIDANCE", ""),
            use_llm_provider=use_llm_provider,
            llm_provider_url=llm_provider_url,
            llm_provider_key=llm_provider_key,
            port=int(_env("PORT", "8000")),
        )
