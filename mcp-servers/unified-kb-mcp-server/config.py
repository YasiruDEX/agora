"""Instance-level configuration for the Unified KB MCP Server, read from env at startup.

Mirrors how Agent Manager injects ``MCP_SERVER_URL``/``MCP_API_KEY`` into each Citizen
Inquiry Agent instance (see PLAN.md §6): every one of the 5 department instances talks to
the *same* server URL but presents a *different* API key, and that key is what this server
resolves to a department namespace. The key->namespace map below stands in for the mapping
Agent Manager would otherwise manage under ``amp:mcp-server:api-key-manage``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Fictional per-department API keys for the Riverside County demo. In Agent Manager these
# would be minted per-instance and injected as MCP_API_KEY; here they're fixed so the same
# keys can be used to run and test the server locally.
DEFAULT_API_KEYS: dict[str, str] = {
    "kb_live_social-services_8f2a1c": "social-services",
    "kb_live_permits-licensing_3d7e90": "permits-licensing",
    "kb_live_tax-revenue_b14f6a": "tax-revenue",
    "kb_live_records-compliance_e9c024": "records-compliance",
    "kb_live_contact-center_5a6b3d": "contact-center",
}

NAMESPACES: tuple[str, ...] = (
    "social-services",
    "permits-licensing",
    "tax-revenue",
    "records-compliance",
    "contact-center",
)

DEPARTMENT_LABELS: dict[str, str] = {
    "social-services": "Social Services",
    "permits-licensing": "Permits & Licensing",
    "tax-revenue": "Tax & Revenue",
    "records-compliance": "Records & Compliance",
    "contact-center": "Contact Center",
}


def _load_api_keys() -> dict[str, str]:
    """Allow overriding/extending the key map via KB_API_KEYS_JSON for other deployments."""
    raw = os.environ.get("KB_API_KEYS_JSON", "").strip()
    if not raw:
        return dict(DEFAULT_API_KEYS)
    import json

    parsed = json.loads(raw)
    for namespace in parsed.values():
        if namespace not in NAMESPACES:
            raise RuntimeError(f"KB_API_KEYS_JSON maps to unknown namespace: {namespace!r}")
    return parsed


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    db_path: str
    encryption_key: str
    api_keys: dict[str, str] = field(default_factory=dict)

    def resolve_namespace(self, api_key: str | None) -> str | None:
        if not api_key:
            return None
        return self.api_keys.get(api_key)

    @classmethod
    def from_env(cls) -> "Config":
        host = os.environ.get("KB_MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("KB_MCP_PORT", "8100"))
        db_path = os.environ.get(
            "KB_DB_PATH",
            os.path.join(os.path.dirname(__file__), "data", "kb_store.db"),
        )
        encryption_key = os.environ.get("KB_ENCRYPTION_KEY", "").strip()
        if not encryption_key:
            raise RuntimeError(
                "KB_ENCRYPTION_KEY is not set. Generate one with: "
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
