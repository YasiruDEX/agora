"""End-to-end test client for the Permit DB MCP Server.

Run with the server already listening:
    python test_client.py http://127.0.0.1:8101/mcp
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from config import DEFAULT_API_KEYS

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
            text = "".join(block.text for block in result.content if hasattr(block, "text"))
            return bool(result.isError), text


async def run(url: str) -> None:
    building_key = next(k for k, v in DEFAULT_API_KEYS.items() if v == "building-permits")
    business_key = next(k for k, v in DEFAULT_API_KEYS.items() if v == "business-licenses")

    print("== permit_lookup: seeded application is readable ==")
    is_error, text = await call_tool(url, building_key, "permit_lookup", {"permit_number": "BP-2026-00042"})
    check(not is_error, "permit_lookup succeeds for a seeded building permit")
    payload = json.loads(text)
    check(payload["applicant_name"] == "Maria Gutierrez", "decrypted applicant name matches seed data")
    check(payload["status"] == "plan_check", "status matches seed data")

    is_error, text = await call_tool(url, business_key, "permit_lookup", {"permit_number": "BP-2026-00042"})
    check(not is_error, "the business-licenses key can also read a building permit (no partitioning by design)")

    is_error, text = await call_tool(url, building_key, "permit_lookup", {"permit_number": "BP-2026-99999"})
    check(is_error, "unknown permit_number is denied, not silently empty")

    print("\n== fee_schedule_read: known and unknown permit types ==")
    is_error, text = await call_tool(url, building_key, "fee_schedule_read", {"permit_type": "adu_permit", "valuation": 100000})
    check(not is_error, "fee_schedule_read succeeds for adu_permit")
    payload = json.loads(text)
    expected = round(275.0 + 180.0 + (100000 / 1000.0) * 4.0, 2)
    check(payload["estimated_total_fee"] == expected, f"estimated total fee computed correctly ({payload['estimated_total_fee']} == {expected})")

    is_error, text = await call_tool(url, building_key, "fee_schedule_read", {"permit_type": "not_a_real_type"})
    check(is_error, "unknown permit_type is denied with a helpful error")

    print("\n== application_prefill: creates a new draft application ==")
    is_error, text = await call_tool(
        url,
        business_key,
        "application_prefill",
        {
            "permit_type": "business_license",
            "applicant_name": "Test Applicant",
            "applicant_email": "test.applicant@example.com",
            "applicant_phone": "951-555-0100",
            "property_address": "100 Test St, Riverside County, CA",
        },
    )
    check(not is_error, "application_prefill succeeds")
    payload = json.loads(text)
    check(payload["status"] == "draft", "new application starts in draft status")
    check(payload["permit_number"].startswith("BL-"), "business license gets a BL- prefixed permit number")
    new_permit_number = payload["permit_number"]

    is_error, text = await call_tool(url, building_key, "permit_lookup", {"permit_number": new_permit_number})
    check(not is_error, "the newly created draft application is immediately readable via permit_lookup")
    payload = json.loads(text)
    check(payload["applicant_name"] == "Test Applicant", "prefilled applicant name round-trips correctly")

    print("\n== Invalid / missing API key is denied ==")
    is_error, text = await call_tool(url, "not-a-real-key", "permit_lookup", {"permit_number": "BP-2026-00042"})
    check(is_error, "invalid API key is denied")
    is_error, text = await call_tool(url, None, "permit_lookup", {"permit_number": "BP-2026-00042"})
    check(is_error, "missing API key is denied")

    print("\n" + "=" * 60)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("All checks PASSED.")


if __name__ == "__main__":
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8101/mcp"
    asyncio.run(run(server_url))
