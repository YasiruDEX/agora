"""Loads tools from both MCP servers this agent talks to: Permit DB (dedicated, full access)
and State ID Verification (external stand-in, single shared integration credential).

Both Permit & Licensing instances (Building Permits, Business Licenses) connect to the same
two server URLs — the values differ per instance only in which API keys are injected, not in
which servers are reachable (PLAN.md §5/§6).
"""

from __future__ import annotations

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from config import Config


def _headers(api_key: str) -> dict[str, str]:
    # Same dual-header approach as the Citizen Inquiry Agent: works whether MCP_SERVER_URL
    # points directly at the backend (checks X-MCP-API-Key) or at an Agent Manager MCP proxy
    # (checks API-Key, then forwards with its own configured backend header).
    return {"X-MCP-API-Key": api_key, "API-Key": api_key, "Authorization": ""}


async def load_permit_tools(cfg: Config) -> list[BaseTool]:
    client = MultiServerMCPClient(
        {
            "permit-db": {
                "transport": "streamable_http",
                "url": cfg.permitdb_mcp_server_url,
                "headers": _headers(cfg.permitdb_mcp_api_key),
            },
            "state-id-verification": {
                "transport": "streamable_http",
                "url": cfg.stateid_mcp_server_url,
                "headers": _headers(cfg.stateid_mcp_api_key),
            },
        }
    )
    return await client.get_tools()
