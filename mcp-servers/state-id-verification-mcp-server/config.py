"""Instance-level configuration for the State ID Verification MCP Server.

Stands in for an external, third-party service (PLAN.md §5: "Dedicated Permit DB MCP +
external State ID Verification MCP") — the county doesn't run or own this system in real
life, it just holds one integration credential to call it. There's exactly one API key here,
not a per-department map, because there's exactly one integration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_API_KEY = "stateid_ext_riverside-county_9k2m7p"


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    api_key: str
    seed_path: str

    @classmethod
    def from_env(cls) -> "Config":
        host = os.environ.get("STATEID_MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("STATEID_MCP_PORT", "8102"))
        api_key = os.environ.get("STATEID_API_KEY", DEFAULT_API_KEY).strip()
        seed_path = os.environ.get(
            "STATEID_SEED_PATH",
            os.path.join(os.path.dirname(__file__), "seed", "state_id_registry.json"),
        )
        return cls(host=host, port=port, api_key=api_key, seed_path=seed_path)
