"""Unified KB MCP Server — namespace-partitioned knowledge base for Riverside County's
Citizen Inquiry Agent (PLAN.md §6).

One server, four tools (kb_search, kb_read, kb_write, kb_list_sources), five department
namespaces. Every Citizen Inquiry instance authenticates with the same MCP_SERVER_URL but a
different MCP_API_KEY; this server resolves that key to exactly one namespace and every tool
call is scoped to it — a department's agent instance cannot read or write another
department's articles even though the tool surface looks identical.
"""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import Context, FastMCP

from config import Config, DEPARTMENT_LABELS
from seed_data import seed_all
from store import KBStore

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("unified-kb-mcp")

CONFIG = Config.from_env()
STORE = KBStore(CONFIG.db_path, CONFIG.encryption_key)

mcp = FastMCP(
    "unified-kb",
    instructions=(
        "Namespace-scoped knowledge base for Riverside County Department of Citizen "
        "Services. Every call is automatically scoped to the caller's department based on "
        "their API key — there is no way to search, read, or write another department's "
        "articles through this server."
    ),
    host=CONFIG.host,
    port=CONFIG.port,
)


def _extract_api_key(request) -> str | None:
    if request is None:
        return None
    api_key = request.headers.get("x-mcp-api-key")
    if api_key:
        return api_key
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _resolve_namespace(ctx: Context) -> str:
    request = ctx.request_context.request
    api_key = _extract_api_key(request)
    namespace = CONFIG.resolve_namespace(api_key)
    if namespace is None:
        raise ValueError(
            "Access denied: missing or unrecognized MCP API key. Set the X-MCP-API-Key "
            "header (or Authorization: Bearer <key>) to a valid department key."
        )
    return namespace


@mcp.tool()
def kb_search(query: str, ctx: Context) -> str:
    """Semantic search over the caller's department knowledge-base namespace.

    Returns up to 5 matching articles ranked by relevance, each with its doc_id, source
    title, a content snippet, and a relevance score. Only searches the namespace the
    caller's API key resolves to.
    """
    namespace = _resolve_namespace(ctx)
    results = STORE.search(namespace, query)
    payload = [
        {
            "doc_id": doc.doc_id,
            "source": doc.source,
            "snippet": doc.content[:280] + ("..." if len(doc.content) > 280 else ""),
            "score": round(score, 3),
        }
        for doc, score in results
    ]
    return json.dumps({"namespace": namespace, "query": query, "results": payload})


@mcp.tool()
def kb_read(doc_id: str, ctx: Context) -> str:
    """Fetch the full content of a specific knowledge-base article by doc_id.

    Only articles within the caller's department namespace are visible; an unknown or
    out-of-namespace doc_id returns a not-found error, never another department's content.
    """
    namespace = _resolve_namespace(ctx)
    doc = STORE.read(namespace, doc_id)
    if doc is None:
        raise ValueError(f"No article '{doc_id}' found in the '{namespace}' namespace.")
    return json.dumps(
        {
            "namespace": doc.namespace,
            "doc_id": doc.doc_id,
            "source": doc.source,
            "content": doc.content,
            "updated_at": doc.updated_at,
        }
    )


@mcp.tool()
def kb_write(doc_id: str, content: str, ctx: Context, source: str = "agent-authored") -> str:
    """Create or update a knowledge-base article in the caller's department namespace.

    If doc_id already exists in the namespace it is updated in place; otherwise a new
    article is created. Writes never cross into another department's namespace.
    """
    namespace = _resolve_namespace(ctx)
    doc = STORE.upsert(namespace=namespace, doc_id=doc_id, source=source, content=content)
    return json.dumps(
        {
            "namespace": doc.namespace,
            "doc_id": doc.doc_id,
            "source": doc.source,
            "updated_at": doc.updated_at,
            "status": "written",
        }
    )


@mcp.tool()
def kb_list_sources(ctx: Context) -> str:
    """List the distinct source documents the caller's namespace was built from."""
    namespace = _resolve_namespace(ctx)
    sources = STORE.list_sources(namespace)
    return json.dumps(
        {
            "namespace": namespace,
            "department": DEPARTMENT_LABELS.get(namespace, namespace),
            "sources": sources,
            "count": len(sources),
        }
    )


def main() -> None:
    seeded = seed_all(STORE)
    log.info("Seeded namespaces: %s", seeded)
    log.info(
        "Unified KB MCP Server listening on http://%s:%s/mcp (namespaces=%s)",
        CONFIG.host,
        CONFIG.port,
        list(CONFIG.api_keys.values()),
    )
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
