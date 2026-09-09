"""Loads tools from both MCP servers this agent talks to: Permit DB (dedicated, full access)
and State ID Verification (external stand-in, single shared integration credential) — via
Agent Manager's AgentID OAuth2 proxy in front of each.

Both Permit & Licensing instances (Building Permits, Business Licenses) connect to the same
two server URLs — the values differ per instance only in which AgentID credentials are
injected, not in which servers are reachable (PLAN.md §5/§6).

One AgentID identity, two MCP resources: a separate access token is minted per MCP server URL
(the OAuth2 `resource` parameter, RFC 8707, differs per server), but both token requests use
the same client-credentials grant (RFC 6749) against the same token endpoint. Each token is
cached and refreshed independently, ahead of its own expiry — see `_TokenCache`.

The token is short-lived and MUST be refreshed, not fetched once and reused for the life of
the process: a stale token doesn't fail cleanly here — the LangChain MCP tool wrappers open a
fresh connection per tool call, so an expired token makes that connection setup fail deep
inside `langchain-mcp-adapters`/`mcp`, outside any of our own error handling, and surfaces as
an opaque ``ExceptionGroup: unhandled errors in a TaskGroup`` instead of a clean auth-denied
message. `app.py` also rebuilds the tool set (and therefore the agent) on every `/chat`
request rather than once at startup, so a request is never served against a token that was
already stale when the process started.
"""

from __future__ import annotations

import time
from typing import Any

import requests
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from config import Config

_EXPIRY_SAFETY_MARGIN_SECONDS = 30.0
_DEFAULT_ASSUMED_TTL_SECONDS = 60.0


class _TokenCache:
    """Per-process cache of AgentID access tokens, keyed by MCP resource URL.

    One client identity can hold tokens for multiple resources at once — each resource's
    token is fetched and refreshed independently.
    """

    def __init__(self) -> None:
        self._tokens: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}

    def get(self, cfg: Config, resource_url: str) -> str:
        now = time.monotonic()
        if resource_url not in self._tokens or now >= self._expires_at.get(resource_url, 0.0):
            token, ttl = _request_access_token(cfg, resource_url)
            self._tokens[resource_url] = token
            self._expires_at[resource_url] = now + max(ttl - _EXPIRY_SAFETY_MARGIN_SECONDS, 0.0)
        return self._tokens[resource_url]


_token_cache = _TokenCache()


def _request_access_token(cfg: Config, resource_url: str) -> tuple[str, float]:
    token_response = requests.post(
        cfg.agentid_token_endpoint,
        auth=(cfg.agentid_client_id, cfg.agentid_client_secret),
        data={
            "grant_type": "client_credentials",
            "scope": cfg.agentid_scopes,
            # RFC 8707 resource indicator — binds the token to this specific MCP endpoint.
            "resource": resource_url,
        },
        timeout=30,
    )
    token_response.raise_for_status()
    body = token_response.json()
    ttl = float(body.get("expires_in", _DEFAULT_ASSUMED_TTL_SECONDS))
    return body["access_token"], ttl


async def load_permit_tools(cfg: Config) -> list[BaseTool]:
    """Build fresh MCP tool bindings for both servers, each with a currently-valid token.

    Call this once per request (see app.py), not once at process startup.
    """
    server_configs: dict[str, dict[str, Any]] = {}

    if cfg.permitdb_mcp_server_url:
        permitdb_token = _token_cache.get(cfg, cfg.permitdb_mcp_server_url)
        server_configs["permit-db"] = {
            "url": cfg.permitdb_mcp_server_url,
            "transport": "streamable_http",
            "headers": {"Authorization": f"Bearer {permitdb_token}"},
        }

    if cfg.stateid_mcp_server_url:
        stateid_token = _token_cache.get(cfg, cfg.stateid_mcp_server_url)
        server_configs["state-id-verification"] = {
            "url": cfg.stateid_mcp_server_url,
            "transport": "streamable_http",
            "headers": {"Authorization": f"Bearer {stateid_token}"},
        }

    if not server_configs:
        return []

    client = MultiServerMCPClient(server_configs)
    return await client.get_tools()
