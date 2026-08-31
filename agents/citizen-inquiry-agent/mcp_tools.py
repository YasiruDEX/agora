"""Loads the Unified KB MCP server's tools via Agent Manager's AgentID OAuth2 proxy.

Every Citizen Inquiry instance points at the same MCP_SERVER_URL and gets back the same four
tool names (kb_search, kb_read, kb_write, kb_list_sources) — namespace resolution still
happens on the MCP server side (see mcp-servers/unified-kb-mcp-server), unchanged.

What changed is how this agent authenticates to get there: MCP_SERVER_URL now points at an
MCP proxy in front of the real server, and that proxy expects an OAuth2 access token, not a
static API key. So before connecting:

  1. MCP_SERVER_URL is also the OAuth2 *resource* (RFC 8707) — it has to be known before
     minting the token, not just before calling the tool.
  2. Request a token using the AgentID service-account credentials Agent Manager injects
     (AMP_AGENTID_CLIENT_ID/SECRET/TOKEN_ENDPOINT/SCOPES), scoped to this resource via the
     `resource` parameter on the client_credentials grant (RFC 6749 + RFC 8707).
  3. Call the proxy with that token as a normal `Authorization: Bearer` header.

The proxy is the one translating that Bearer token into whatever the real Unified KB MCP
server still expects (X-MCP-API-Key) — this agent never sees or sends that header itself.

The token is short-lived and MUST be refreshed, not fetched once and reused for the life of
the process: client-credentials tokens typically expire in minutes, and a stale token doesn't
fail cleanly here — the LangChain MCP tool wrappers open a fresh connection per tool call, so
an expired token makes that connection setup fail deep inside `langchain-mcp-adapters`/`mcp`,
outside any of our own error handling, and surfaces as an opaque
``ExceptionGroup: unhandled errors in a TaskGroup`` instead of a clean auth-denied message.
`_TokenCache` below re-fetches ahead of expiry so callers always get a live token; `app.py`
also rebuilds the tool set (and therefore the agent) on every `/chat` request rather than once
at startup, so a request is never served against a token that was already stale when the
process started.
"""

from __future__ import annotations

import time
from typing import Any

import requests
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from config import Config

# Refresh this many seconds before the token's reported expiry, to avoid a request racing
# past expiry mid-flight (e.g. a token that expires between us checking it's "valid" and the
# proxy actually receiving the request).
_EXPIRY_SAFETY_MARGIN_SECONDS = 30.0
# Fallback lifetime to assume if the token response omits ``expires_in`` (not all OAuth2
# servers return it, though RFC 6749 recommends it) — conservative, forces frequent refresh
# rather than risking reuse of a token that's already gone stale.
_DEFAULT_ASSUMED_TTL_SECONDS = 60.0


class _TokenCache:
    """Per-process cache for the AgentID access token, keyed by (resource, scopes).

    A single Citizen Inquiry instance only ever talks to one MCP resource with one scope set,
    so a single cached entry is enough — this just avoids hitting the token endpoint on every
    tool call when the previous token is still comfortably valid.
    """

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: float = 0.0

    def get(self, cfg: Config) -> str:
        now = time.monotonic()
        if self._token is None or now >= self._expires_at:
            self._token, ttl = _request_access_token(cfg)
            self._expires_at = now + max(ttl - _EXPIRY_SAFETY_MARGIN_SECONDS, 0.0)
        return self._token


_token_cache = _TokenCache()


def _request_access_token(cfg: Config) -> tuple[str, float]:
    token_response = requests.post(
        cfg.agentid_token_endpoint,
        auth=(cfg.agentid_client_id, cfg.agentid_client_secret),
        data={
            "grant_type": "client_credentials",
            "scope": cfg.agentid_scopes,
            # RFC 8707 resource indicator — binds the token to this specific MCP endpoint.
            "resource": cfg.mcp_server_url,
        },
        timeout=30,
    )
    token_response.raise_for_status()
    body = token_response.json()
    ttl = float(body.get("expires_in", _DEFAULT_ASSUMED_TTL_SECONDS))
    return body["access_token"], ttl


async def load_kb_tools(cfg: Config) -> list[BaseTool]:
    """Build fresh MCP tool bindings, authenticated with a currently-valid access token.

    Call this once per request (see app.py), not once at process startup — the returned tool
    objects capture the token in their connection config at construction time, so reusing
    tools built at startup would mean replaying an increasingly stale token forever.
    """
    if not cfg.mcp_server_url:
        return []

    access_token = _token_cache.get(cfg)

    server_configs: dict[str, dict[str, Any]] = {
        "unified-kb": {
            "url": cfg.mcp_server_url,
            "transport": "streamable_http",
            "headers": {"Authorization": f"Bearer {access_token}"},
        }
    }

    client = MultiServerMCPClient(server_configs)
    return await client.get_tools()
