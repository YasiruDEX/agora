"""Instance-level configuration for the Permit DB MCP Server, read from env at startup.

Unlike the Unified KB MCP Server, this server is not namespace-partitioned — both Permit &
Licensing Agent instances (Building Permits, Business Licenses) share the same full-access
dataset (PLAN.md §6). API keys here are purely authentication: a valid key gets full access,
an invalid/missing one is denied. There's no per-key data boundary to enforce because there's
only one department behind this server.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Fictional API keys for the Riverside County demo — minted per Permit & Licensing instance
# under amp:mcp-server:api-key-manage in the real deployment, fixed here for local dev/testing.
DEFAULT_API_KEYS: dict[str, str] = {
    "permitdb_live_building-permits_7c1a4e": "building-permits",
    "permitdb_live_business-licenses_2f9b6d": "business-licenses",
}


def _load_api_keys() -> dict[str, str]:
    raw = os.environ.get("PERMITDB_API_KEYS_JSON", "").strip()
    if not raw:
        return dict(DEFAULT_API_KEYS)
    import json

    return json.loads(raw)


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    db_path: str
    encryption_key: str
    api_keys: dict[str, str] = field(default_factory=dict)

    def caller_label(self, api_key: str | None) -> str | None:
        if not api_key:
            return None
        return self.api_keys.get(api_key)

    @classmethod
    def from_env(cls) -> "Config":
        host = os.environ.get("PERMITDB_MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("PERMITDB_MCP_PORT", "8101"))
        db_path = os.environ.get(
            "PERMITDB_DB_PATH",
            os.path.join(os.path.dirname(__file__), "data", "permit_db.db"),
        )
        encryption_key = os.environ.get("PERMITDB_ENCRYPTION_KEY", "").strip()
        if not encryption_key:
            raise RuntimeError(
                "PERMITDB_ENCRYPTION_KEY is not set. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; "
                'print(Fernet.generate_key().decode())"'
            )
        return cls(
            host=host,
            port=port,
            db_path=db_path,
            encryption_key=encryption_key,
            api_keys=_load_api_keys(),
        )
