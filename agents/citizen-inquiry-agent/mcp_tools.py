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
"""

from __future__ import annotations

from typing import Any

import requests
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from config import Config


def _fetch_access_token(cfg: Config) -> str:
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
    return token_response.json()["access_token"]


async def load_kb_tools(cfg: Config) -> list[BaseTool]:
    if not cfg.mcp_server_url:
        return []

    access_token = _fetch_access_token(cfg)

    server_configs: dict[str, dict[str, Any]] = {
        "unified-kb": {
            "url": cfg.mcp_server_url,
            "transport": "streamable_http",
            "headers": {"Authorization": f"Bearer {access_token}"},
        }
    }

    client = MultiServerMCPClient(server_configs)
    return await client.get_tools()
