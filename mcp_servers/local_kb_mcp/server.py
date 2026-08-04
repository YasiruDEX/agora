"""MCP stdio/SSE server exposing search_knowledge_base over a local RAG index.

No external vector DB is involved (this replaces the old Pinecone-backed
mcp_servers/pinecone_kb_mcp). The knowledge base (Markdown under
knowledge_base/<department>/) is chunked and embedded with OpenAI, cached to
kb_index_cache.json next to this file (see kb_index.py), and searched in
memory with cosine similarity. If the cache is missing or a KB file changed,
it's (re)built automatically on startup.
"""
import os
import sys

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from openai import OpenAI

import kb_index

load_dotenv()

REQUIRED_ENV = ["OPENAI_API_KEY"]
missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
if missing:
    print(f"ERROR: missing required environment variables: {', '.join(missing)}", file=sys.stderr)
    sys.exit(1)

_openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

print("[local-kb] building/loading local KB index...", file=sys.stderr)
_index = kb_index.build_index(_openai, log=lambda msg: print(f"[local-kb] {msg}", file=sys.stderr))
_namespace_counts = {ns: sum(len(e["chunks"]) for e in files.values()) for ns, files in _index.items()}
print(f"[local-kb] index ready: {_namespace_counts}", file=sys.stderr)

# MCP_TRANSPORT selects "stdio" (default, for local subprocess use) or "sse"/
# "streamable-http" to run this as a standalone network service that agents
# connect to remotely via MCP_*_URL env vars instead of spawning it locally.
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "9001"))

mcp = FastMCP("local-kb", host=MCP_HOST, port=MCP_PORT)


@mcp.tool()
def search_knowledge_base(namespace: str, query: str, top_k: int = 5) -> str:
    """Semantic search over the local department knowledge base.

    Args:
        namespace: Namespace to search, e.g. 'permits-licensing',
            'tax-revenue', 'social-services', 'health-environment', 'records-compliance'.
        query: Natural language citizen question to search for.
        top_k: Number of matching chunks to return (default 5).
    """
    print(f"[local-kb] search_knowledge_base called: namespace={namespace!r} query={query!r} top_k={top_k}", file=sys.stderr)

    matches = kb_index.search(_index, _openai, namespace, query, top_k=top_k)
    if not matches:
        return f"No results found in namespace '{namespace}' for query: {query}"

    lines = []
    for i, match in enumerate(matches, start=1):
        lines.append(
            f"[{i}] (score={match['score']:.3f}, source_file={match['source_file']}, "
            f"department={match['department']})\n{match['text']}"
        )

    return "\n\n".join(lines)


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport != "stdio":
        print(f"[local-kb-mcp] serving over {transport} at {MCP_HOST}:{MCP_PORT}", file=sys.stderr)
    mcp.run(transport=transport)
