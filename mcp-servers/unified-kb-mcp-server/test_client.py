"""End-to-end test client for the Unified KB MCP Server.

Connects over streamable-http as five different "agent instances" (one per department API
key) plus one invalid key, and asserts:
  - each key only ever sees its own department's namespace/sources
  - kb_search / kb_read return department-appropriate content
  - kb_write + kb_read round-trips within a namespace
  - cross-namespace doc_id reads are denied (not leaked)
  - an invalid/missing API key is denied outright

Run with the server already listening (see README), e.g.:
    python test_client.py http://127.0.0.1:8100/mcp
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from config import DEFAULT_API_KEYS, DEPARTMENT_LABELS

PASS = "PASS"
FAIL = "FAIL"
_failures: list[str] = []


def check(condition: bool, description: str) -> None:
    status = PASS if condition else FAIL
    print(f"[{status}] {description}")
    if not condition:
        _failures.append(description)


async def call_tool(url: str, api_key: str | None, tool: str, args: dict) -> tuple[bool, str]:
    headers = {"X-MCP-API-Key": api_key} if api_key else {}
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            text = "".join(
                block.text for block in result.content if hasattr(block, "text")
            )
            return bool(result.isError), text


async def run(url: str) -> None:
    namespaces_by_key = DEFAULT_API_KEYS
    keys_by_namespace = {ns: key for key, ns in namespaces_by_key.items()}

    print("== kb_list_sources: each department sees only its own sources ==")
    for key, namespace in namespaces_by_key.items():
        is_error, text = await call_tool(url, key, "kb_list_sources", {})
        check(not is_error, f"{namespace}: kb_list_sources succeeded")
        payload = json.loads(text)
        check(
            payload.get("namespace") == namespace,
            f"{namespace}: response namespace matches caller's key ({payload.get('namespace')!r})",
        )
        check(
            payload.get("department") == DEPARTMENT_LABELS[namespace],
            f"{namespace}: department label resolved correctly",
        )
        check(payload.get("count", 0) > 0, f"{namespace}: has seeded sources ({payload.get('count')})")

    print("\n== kb_search: results stay within the caller's namespace ==")
    social_key = keys_by_namespace["social-services"]
    is_error, text = await call_tool(url, social_key, "kb_search", {"query": "CalFresh food benefits"})
    check(not is_error, "social-services: kb_search succeeded")
    payload = json.loads(text)
    check(len(payload["results"]) > 0, "social-services: kb_search found relevant results")
    check(
        all(r["doc_id"].startswith("ss-") for r in payload["results"]),
        "social-services: all search results are social-services docs (ss-*)",
    )

    tax_key = keys_by_namespace["tax-revenue"]
    is_error, text = await call_tool(url, tax_key, "kb_search", {"query": "CalFresh food benefits"})
    check(not is_error, "tax-revenue: kb_search on a social-services topic still succeeds (empty is fine)")
    payload = json.loads(text)
    check(
        all(not r["doc_id"].startswith("ss-") for r in payload["results"]),
        "tax-revenue: no social-services docs leak into tax-revenue's search results",
    )

    print("\n== kb_read: cross-namespace doc_id is denied, not leaked ==")
    is_error, text = await call_tool(url, tax_key, "kb_read", {"doc_id": "ss-001"})
    check(is_error, "tax-revenue: reading a social-services doc_id (ss-001) is denied")
    check("CalFresh" not in text, "tax-revenue: denied read does not leak social-services content")

    is_error, text = await call_tool(url, social_key, "kb_read", {"doc_id": "ss-001"})
    check(not is_error, "social-services: reading its own doc_id (ss-001) succeeds")
    payload = json.loads(text)
    check("CalFresh" in payload["content"], "social-services: read content matches expected article")

    print("\n== kb_write + kb_read round trip within a namespace ==")
    permits_key = keys_by_namespace["permits-licensing"]
    write_doc_id = "pl-999-test"
    is_error, text = await call_tool(
        url,
        permits_key,
        "kb_write",
        {"doc_id": write_doc_id, "content": "Test article about ADU permit fast-track pilot.", "source": "test-suite"},
    )
    check(not is_error, "permits-licensing: kb_write succeeded")
    is_error, text = await call_tool(url, permits_key, "kb_read", {"doc_id": write_doc_id})
    check(not is_error, "permits-licensing: reading back the written doc succeeded")
    payload = json.loads(text)
    check(
        "ADU permit fast-track" in payload["content"],
        "permits-licensing: written content matches what was read back",
    )

    is_error, text = await call_tool(url, tax_key, "kb_read", {"doc_id": write_doc_id})
    check(is_error, "tax-revenue: cannot read the article permits-licensing just wrote")

    print("\n== Invalid / missing API key is denied ==")
    is_error, text = await call_tool(url, "not-a-real-key", "kb_list_sources", {})
    check(is_error, "invalid API key: kb_list_sources is denied")

    is_error, text = await call_tool(url, None, "kb_list_sources", {})
    check(is_error, "missing API key: kb_list_sources is denied")

    print("\n" + "=" * 60)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("All checks PASSED.")


if __name__ == "__main__":
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8100/mcp"
    asyncio.run(run(server_url))
