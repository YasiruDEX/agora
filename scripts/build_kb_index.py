"""Explicitly (re)build the local KB index used by mcp_servers/local_kb_mcp.

Not required for normal use -- the MCP server builds/refreshes this index
itself on startup. This script exists for CI/deploy pipelines that want to
pre-warm the index (or force a full rebuild with --force) without spinning up
the server. See mcp_servers/local_kb_mcp/kb_index.py for the actual chunk/
embed/cache logic.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp_servers" / "local_kb_mcp"))
import kb_index  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def main():
    load_dotenv(REPO_ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is required to build the local KB index.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    force = "--force" in sys.argv
    index = kb_index.build_index(client, force=force, log=print)

    print("\n=== Local KB Index Summary ===")
    total = 0
    for namespace, files in sorted(index.items()):
        chunk_count = sum(len(entry["chunks"]) for entry in files.values())
        total += chunk_count
        print(f"  {namespace:25s} files={len(files):3d}  chunks={chunk_count:4d}")
    print(f"\nTotal chunks indexed: {total}")
    print(f"Cache written to: {kb_index.CACHE_PATH}")


if __name__ == "__main__":
    main()
