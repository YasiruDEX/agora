"""Loads the Unified KB MCP server's tools, scoped by this instance's MCP_API_KEY.

Every Citizen Inquiry instance points at the same MCP_SERVER_URL and gets back the same four
tool names (kb_search, kb_read, kb_write, kb_list_sources) — the only thing that differs
between department instances is the API key sent on every call, which the server resolves to
one department namespace (see mcp-servers/unified-kb-mcp-server).
"""

from __future__ import annotations

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from config import Config


async def load_kb_tools(cfg: Config) -> list[BaseTool]:
    client = MultiServerMCPClient(
        {
            "unified-kb": {
                "transport": "streamable_http",
                "url": cfg.mcp_server_url,
                "headers": {"X-MCP-API-Key": cfg.mcp_api_key},
            }
        }
    )
    return await client.get_tools()
