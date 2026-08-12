"""Instance-level configuration for the Case Management MCP Server.

This is the centerpiece MCP-scoping demo (PLAN.md §7-8) and has two independent boundaries
stacked on top of each other, both enforced here since there's no Agent Manager in the loop
for local testing:

  1. MCP tool scope — the Case Management Agent's identity (one API key) is granted exactly
     three of the server's seven tools: case_search, case_read, case_notes_write. Calling any
     of the other four is denied before it reaches the encrypted store, not silently ignored.
  2. On-behalf-of identity — every call must also carry an opaque access token identifying
     *which caseworker* the agent is acting for. The server "introspects" that token (a local
     stand-in for RFC 7662 introspection against the county's real IDP) and filters
     case_search/case_read/case_notes_write to that caseworker's own assigned cases. The
     agent's own API key never grants god-mode access to every case.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# The Case Management Agent's single MCP identity/API key, and exactly which of the 7 tools
# it's scoped into. Everything else is a scope violation, not a missing-key error.
DEFAULT_API_KEY = "casemgmt_live_case-management-agent_6b8f31"
SCOPED_TOOLS: frozenset[str] = frozenset({"case_search", "case_read", "case_notes_write"})
ALL_TOOLS: frozenset[str] = frozenset(
    {
        "case_search",
        "case_read",
        "case_notes_write",
        "case_status_update",
        "citizen_profile_read",
        "citizen_profile_write",
        "case_close",
    }
)

# Opaque on-behalf-of tokens -> caseworker identity. Stands in for the county's IDP issuing
# tokens the MCP server introspects via RFC 7662, per PLAN.md §8.
DEFAULT_OBO_TOKENS: dict[str, dict[str, str]] = {
    "obo_joan_ellis_4a7c9f": {"caseworker_id": "joan.ellis", "name": "Joan Ellis"},
    "obo_renee_alvarez_1e6b2d": {"caseworker_id": "renee.alvarez", "name": "Renee Alvarez"},
}


def _load_obo_tokens() -> dict[str, dict[str, str]]:
    raw = os.environ.get("CASEMGMT_OBO_TOKENS_JSON", "").strip()
    if not raw:
        return dict(DEFAULT_OBO_TOKENS)
    import json

    return json.loads(raw)


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    db_path: str
    encryption_key: str
    api_key: str
    obo_tokens: dict[str, dict[str, str]] = field(default_factory=dict)

    def introspect(self, token: str | None) -> dict[str, str] | None:
        """RFC 7662-style introspection stand-in: active token -> caseworker identity, or
        None if the token is missing/unknown ('inactive', in RFC 7662 terms)."""
        if not token:
            return None
        return self.obo_tokens.get(token)

    @classmethod
    def from_env(cls) -> "Config":
        host = os.environ.get("CASEMGMT_MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("CASEMGMT_MCP_PORT", "8103"))
        db_path = os.environ.get(
            "CASEMGMT_DB_PATH",
            os.path.join(os.path.dirname(__file__), "data", "case_mgmt.db"),
        )
        encryption_key = os.environ.get("CASEMGMT_ENCRYPTION_KEY", "").strip()
        if not encryption_key:
            raise RuntimeError(
                "CASEMGMT_ENCRYPTION_KEY is not set. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; "
                'print(Fernet.generate_key().decode())"'
            )
        api_key = os.environ.get("CASEMGMT_API_KEY", DEFAULT_API_KEY).strip()
        return cls(
            host=host,
            port=port,
            db_path=db_path,
            encryption_key=encryption_key,
            api_key=api_key,
            obo_tokens=_load_obo_tokens(),
        )
