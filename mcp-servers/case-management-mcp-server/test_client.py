"""End-to-end test client for the Case Management MCP Server.

Exercises both boundaries from PLAN.md §7-8:
  1. MCP tool scope — only case_search/case_read/case_notes_write should succeed; the other
     four tools must be denied even with a valid API key.
  2. On-behalf-of identity — the same API key, with two different caseworker tokens, must see
     two different case lists, and reading/noting another caseworker's case must be denied.

Run with the server already listening:
    python test_client.py http://127.0.0.1:8103/mcp
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from config import DEFAULT_API_KEY, DEFAULT_OBO_TOKENS

PASS = "PASS"
FAIL = "FAIL"
_failures: list[str] = []


def check(condition: bool, description: str) -> None:
    status = PASS if condition else FAIL
    print(f"[{status}] {description}")
    if not condition:
        _failures.append(description)


async def call_tool(
    url: str, api_key: str | None, obo_token: str | None, tool: str, args: dict
) -> tuple[bool, str]:
    headers = {}
    if api_key:
        headers["X-MCP-API-Key"] = api_key
    if obo_token:
        headers["X-OBO-Token"] = obo_token
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            text = "".join(block.text for block in result.content if hasattr(block, "text"))
            return bool(result.isError), text


async def run(url: str) -> None:
    joan_token = next(t for t, v in DEFAULT_OBO_TOKENS.items() if v["caseworker_id"] == "joan.ellis")
    renee_token = next(t for t, v in DEFAULT_OBO_TOKENS.items() if v["caseworker_id"] == "renee.alvarez")

    print("== On-behalf-of identity: same instance, two caseworkers, two case lists ==")
    is_error, text = await call_tool(url, DEFAULT_API_KEY, joan_token, "case_search", {"query": ""})
    check(not is_error, "case_search succeeds for Joan")
    joan_cases = {c["case_id"] for c in json.loads(text)["results"]}
    check(joan_cases == {"CASE-1001", "CASE-1002", "CASE-1003"}, f"Joan sees exactly her 3 assigned cases (got {joan_cases})")

    is_error, text = await call_tool(url, DEFAULT_API_KEY, renee_token, "case_search", {"query": ""})
    check(not is_error, "case_search succeeds for Renee")
    renee_cases = {c["case_id"] for c in json.loads(text)["results"]}
    check(renee_cases == {"CASE-1004", "CASE-1005", "CASE-1006"}, f"Renee sees exactly her 3 assigned cases (got {renee_cases})")

    check(joan_cases.isdisjoint(renee_cases), "same agent identity, same API key — the two caseworkers' case lists never overlap")

    print("\n== case_read / case_notes_write respect case ownership, not just tool scope ==")
    is_error, text = await call_tool(url, DEFAULT_API_KEY, joan_token, "case_read", {"case_id": "CASE-1001"})
    check(not is_error, "Joan can read her own case CASE-1001")

    is_error, text = await call_tool(url, DEFAULT_API_KEY, joan_token, "case_read", {"case_id": "CASE-1004"})
    check(is_error, "Joan is denied reading CASE-1004, which is Renee's case")

    is_error, text = await call_tool(
        url, DEFAULT_API_KEY, renee_token, "case_notes_write", {"case_id": "CASE-1001", "note": "test note"}
    )
    check(is_error, "Renee is denied writing a note on Joan's CASE-1001")

    is_error, text = await call_tool(
        url, DEFAULT_API_KEY, joan_token, "case_notes_write", {"case_id": "CASE-1001", "note": "Reviewed job-search progress; on track."}
    )
    check(not is_error, "Joan can write a note on her own case")
    payload = json.loads(text)
    check(payload["author"] == "Joan Ellis", "note is attributed to the introspected caseworker identity, not a raw API key")

    print("\n== MCP scope violation: 4 tools outside the granted scope are denied ==")
    for tool, args in [
        ("case_status_update", {"case_id": "CASE-1001", "new_status": "closed"}),
        ("citizen_profile_read", {"citizen_id": "CIT-3001"}),
        ("citizen_profile_write", {"citizen_id": "CIT-3001", "notes": "unauthorized edit"}),
        ("case_close", {"case_id": "CASE-1001"}),
    ]:
        is_error, text = await call_tool(url, DEFAULT_API_KEY, joan_token, tool, args)
        check(is_error, f"'{tool}' is denied — outside the agent's granted 3-of-7 MCP scope")
        check("scope" in text.lower(), f"'{tool}' denial message names the MCP scope violation, not a generic error")

    print("\n== Missing/invalid API key or on-behalf-of token is denied ==")
    is_error, text = await call_tool(url, "not-a-real-key", joan_token, "case_search", {"query": ""})
    check(is_error, "invalid API key is denied even with a valid OBO token")

    is_error, text = await call_tool(url, DEFAULT_API_KEY, None, "case_search", {"query": ""})
    check(is_error, "missing on-behalf-of token is denied even with a valid API key")

    is_error, text = await call_tool(url, DEFAULT_API_KEY, "not-a-real-token", "case_search", {"query": ""})
    check(is_error, "invalid/inactive on-behalf-of token is denied")

    print("\n" + "=" * 60)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("All checks PASSED.")


if __name__ == "__main__":
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8103/mcp"
    asyncio.run(run(server_url))
