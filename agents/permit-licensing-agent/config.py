"""Instance-level configuration for the Permit & Licensing Agent, read from env at startup.

One image, one codebase — both instances (Building Permits, Business Licenses) are this same
agent, told apart only by ``PERMIT_TYPE_FOCUS`` and the prompt tuning fields (PLAN.md §5/§6).
Both instances point at the same dedicated Permit DB MCP server (full access, no partitioning)
and the same external State ID Verification MCP server.
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
    permit_type_focus: str

    permitdb_mcp_server_url: str
    permitdb_mcp_api_key: str

    stateid_mcp_server_url: str
    stateid_mcp_api_key: str

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
            permit_type_focus=_env("PERMIT_TYPE_FOCUS"),
            permitdb_mcp_server_url=_env("PERMITDB_MCP_SERVER_URL"),
            permitdb_mcp_api_key=_env("PERMITDB_MCP_API_KEY"),
            stateid_mcp_server_url=_env("STATEID_MCP_SERVER_URL"),
            stateid_mcp_api_key=_env("STATEID_MCP_API_KEY"),
            tone=_env("TONE", "clear, procedural, and precise about fees and timelines"),
            additional_guidance=_env("ADDITIONAL_GUIDANCE", ""),
            use_llm_provider=use_llm_provider,
            llm_provider_url=llm_provider_url,
            llm_provider_key=llm_provider_key,
            port=int(_env("PORT", "8000")),
        )
