"""MCP stdio server exposing search_knowledge_base over our Pinecone knowledge base index.

The official @pinecone-database/mcp package only supports indexes with Pinecone's
integrated inference. Our index is a standard serverless index populated with
externally-generated OpenAI embeddings (see scripts/ingest_kb_pinecone.py), so we
embed queries the same way here and query the index directly.
"""
import os
import sys

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from openai import OpenAI
from pinecone import Pinecone

load_dotenv()

EMBED_MODEL = "text-embedding-3-small"

REQUIRED_ENV = ["PINECONE_API_KEY", "PINECONE_INDEX_NAME", "OPENAI_API_KEY"]
missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
if missing:
    print(f"ERROR: missing required environment variables: {', '.join(missing)}", file=sys.stderr)
    sys.exit(1)

_pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
_index = _pc.Index(os.environ["PINECONE_INDEX_NAME"])
_openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

mcp = FastMCP("pinecone-kb")


@mcp.tool()
def search_knowledge_base(namespace: str, query: str, top_k: int = 5) -> str:
    """Semantic search over the department knowledge base stored in Pinecone.

    Args:
        namespace: Pinecone namespace to search, e.g. 'permits-licensing',
            'tax-revenue', 'social-services', 'health-environment', 'records-compliance'.
        query: Natural language citizen question to search for.
        top_k: Number of matching chunks to return (default 5).
    """
    print(f"[pinecone-kb] search_knowledge_base called: namespace={namespace!r} query={query!r} top_k={top_k}", file=sys.stderr)

    embedding = _openai.embeddings.create(model=EMBED_MODEL, input=query).data[0].embedding

    result = _index.query(
        namespace=namespace,
        vector=embedding,
        top_k=top_k,
        include_metadata=True,
    )

    matches = result.get("matches", []) if isinstance(result, dict) else result.matches
    if not matches:
        return f"No results found in namespace '{namespace}' for query: {query}"

    lines = []
    for i, match in enumerate(matches, start=1):
        metadata = match.metadata if hasattr(match, "metadata") else match.get("metadata", {})
        score = match.score if hasattr(match, "score") else match.get("score")
        text = metadata.get("text", "")
        source_file = metadata.get("source_file", "unknown")
        department = metadata.get("department", "unknown")
        lines.append(
            f"[{i}] (score={score:.3f}, source_file={source_file}, department={department})\n{text}"
        )

    return "\n\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
