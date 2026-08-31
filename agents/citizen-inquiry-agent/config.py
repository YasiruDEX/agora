"""Instance-level configuration for the Citizen Inquiry Agent, read from env at startup.

One image, one codebase — every one of the 5 department instances (Social Services, Permits
& Licensing, Tax & Revenue, Records & Compliance, Contact Center) is this same agent, told
apart only by the env vars Agent Manager injects at deploy time (PLAN.md §5/§6):
``MCP_SERVER_URL`` points at the (proxied) Unified KB MCP endpoint; ``DEPARTMENT_NAME`` only
affects tone/branding in the prompt, never which KB namespace is reachable.

Authentication to the MCP proxy in front of the Unified KB MCP server is OAuth2 client
credentials (RFC 6749) with a resource indicator (RFC 8707), using the AgentID service
account Agent Manager injects: ``AMP_AGENTID_CLIENT_ID`` / ``AMP_AGENTID_CLIENT_SECRET`` /
``AMP_AGENTID_TOKEN_ENDPOINT`` / ``AMP_AGENTID_SCOPES``. The MCP server itself is unchanged —
namespace resolution still happens there, keyed off whatever credential the proxy forwards.
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
    agentid_client_id: str
    agentid_client_secret: str
    agentid_token_endpoint: str
    agentid_scopes: str
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
            agentid_client_id=_env("AMP_AGENTID_CLIENT_ID"),
            agentid_client_secret=_env("AMP_AGENTID_CLIENT_SECRET"),
            agentid_token_endpoint=_env("AMP_AGENTID_TOKEN_ENDPOINT"),
            agentid_scopes=_env("AMP_AGENTID_SCOPES"),
            tone=_env("TONE", "clear, courteous, and plain-language"),
            additional_guidance=_env("ADDITIONAL_GUIDANCE", ""),
            use_llm_provider=use_llm_provider,
            llm_provider_url=llm_provider_url,
            llm_provider_key=llm_provider_key,
            port=int(_env("PORT", "8000")),
        )
