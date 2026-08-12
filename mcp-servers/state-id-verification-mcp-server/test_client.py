"""End-to-end test client for the State ID Verification MCP Server (external stand-in).

Run with the server already listening:
    python test_client.py http://127.0.0.1:8102/mcp
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from config import DEFAULT_API_KEY

PASS = "PASS"
FAIL = "FAIL"
_failures: list[str] = []


def check(condition: bool, description: str) -> None:
    status = PASS if condition else FAIL
    print(f"[{status}] {description}")
    if not condition:
        _failures.append(description)


async def call_tool(url: str, api_key: str | None, args: dict) -> tuple[bool, str]:
    headers = {"X-MCP-API-Key": api_key} if api_key else {}
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("verify_state_id", args)
            text = "".join(block.text for block in result.content if hasattr(block, "text"))
            return bool(result.isError), text


async def run(url: str) -> None:
    print("== verify_state_id: verified match ==")
    is_error, text = await call_tool(
        url,
        DEFAULT_API_KEY,
        {"state_id_number": "CA-DL-D1234567", "full_name": "Maria Gutierrez", "date_of_birth": "1985-03-14"},
    )
    check(not is_error, "verify_state_id succeeds for a matching valid ID")
    payload = json.loads(text)
    check(payload["verdict"] == "verified", "verdict is 'verified' for a correct name/DOB match")

    print("\n== verify_state_id: mismatch is flagged, not silently passed ==")
    is_error, text = await call_tool(
        url,
        DEFAULT_API_KEY,
        {"state_id_number": "CA-DL-D1234567", "full_name": "Someone Else", "date_of_birth": "1985-03-14"},
    )
    check(not is_error, "verify_state_id still returns a normal result (not a tool error) for a mismatch")
    payload = json.loads(text)
    check(payload["verdict"] == "name_or_dob_mismatch", "verdict flags name/DOB mismatch rather than matching anyway")

    print("\n== verify_state_id: unknown ID number ==")
    is_error, text = await call_tool(
        url,
        DEFAULT_API_KEY,
        {"state_id_number": "CA-DL-D0000000", "full_name": "Nobody", "date_of_birth": "2000-01-01"},
    )
    payload = json.loads(text)
    check(payload["verdict"] == "not_found", "unknown state_id_number returns 'not_found'")

    print("\n== verify_state_id: expired / suspended IDs are flagged inactive ==")
    is_error, text = await call_tool(
        url,
        DEFAULT_API_KEY,
        {"state_id_number": "CA-SID-S2233445", "full_name": "Angela Ortiz", "date_of_birth": "1990-07-22"},
    )
    payload = json.loads(text)
    check(payload["verdict"] == "inactive" and payload["status"] == "expired", "expired ID is flagged inactive/expired, not verified")

    is_error, text = await call_tool(
        url,
        DEFAULT_API_KEY,
        {"state_id_number": "CA-DL-D9988776", "full_name": "Robert Kim", "date_of_birth": "1972-01-30"},
    )
    payload = json.loads(text)
    check(payload["verdict"] == "inactive" and payload["status"] == "suspended", "suspended ID is flagged inactive/suspended, not verified")

    print("\n== Invalid / missing integration credential is denied ==")
    is_error, text = await call_tool(
        url, "not-the-real-credential", {"state_id_number": "CA-DL-D1234567", "full_name": "Maria Gutierrez", "date_of_birth": "1985-03-14"}
    )
    check(is_error, "wrong credential is denied")
    is_error, text = await call_tool(
        url, None, {"state_id_number": "CA-DL-D1234567", "full_name": "Maria Gutierrez", "date_of_birth": "1985-03-14"}
    )
    check(is_error, "missing credential is denied")

    print("\n" + "=" * 60)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("All checks PASSED.")


if __name__ == "__main__":
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8102/mcp"
    asyncio.run(run(server_url))
