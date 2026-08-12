"""State ID Verification MCP Server — stand-in for an external, third-party service.

Simulates the state DMV/ID registry the Permit & Licensing Agent checks before acting on an
applicant's identity (PLAN.md §5). The county doesn't own this system in real life; it just
holds one integration credential. Deliberately smaller than the county's own MCP servers —
one tool, no partitioning, no writes, read-only lookups against a static mock registry.
"""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import Context, FastMCP

from config import Config

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("state-id-verification-mcp")

CONFIG = Config.from_env()

with open(CONFIG.seed_path, encoding="utf-8") as f:
    _REGISTRY: list[dict] = json.load(f)
_BY_ID_NUMBER = {rec["state_id_number"]: rec for rec in _REGISTRY}

mcp = FastMCP(
    "state-id-verification",
    instructions=(
        "External state ID verification service (stand-in). Verifies whether a name, date "
        "of birth, and state ID number match a valid record before the county acts on an "
        "applicant's claimed identity."
    ),
    host=CONFIG.host,
    port=CONFIG.port,
)


def _extract_api_key(request) -> str | None:
    if request is None:
        return None
    api_key = request.headers.get("x-mcp-api-key") or request.headers.get("api-key")
    if api_key:
        return api_key
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _require_auth(ctx: Context) -> None:
    request = ctx.request_context.request
    api_key = _extract_api_key(request)
    if api_key != CONFIG.api_key:
        raise ValueError(
            "Access denied: missing or invalid integration credential for the State ID "
            "Verification service."
        )


@mcp.tool()
def verify_state_id(
    state_id_number: str,
    full_name: str,
    date_of_birth: str,
    ctx: Context,
) -> str:
    """Verify a state-issued ID (driver's license or state ID card) against the state registry.

    Pass the state_id_number exactly as presented (e.g. 'CA-DL-D1234567'), the applicant's
    full name, and date_of_birth as YYYY-MM-DD. Returns a verdict: 'verified' (name and DOB
    match an active record), 'name_or_dob_mismatch' (ID number exists but details don't
    match — possible fraud, do not proceed), 'not_found' (no such ID in the registry), or
    'inactive' (ID number and details match but the ID itself is expired or suspended).
    """
    _require_auth(ctx)
    record = _BY_ID_NUMBER.get(state_id_number.strip())
    if record is None:
        return json.dumps({"verdict": "not_found", "state_id_number": state_id_number})

    name_matches = record["full_name"].strip().lower() == full_name.strip().lower()
    dob_matches = record["date_of_birth"] == date_of_birth.strip()

    if not (name_matches and dob_matches):
        return json.dumps(
            {
                "verdict": "name_or_dob_mismatch",
                "state_id_number": state_id_number,
            }
        )

    if record["status"] != "valid":
        return json.dumps(
            {
                "verdict": "inactive",
                "state_id_number": state_id_number,
                "status": record["status"],
                "id_type": record["id_type"],
                "expires_on": record["expires_on"],
            }
        )

    return json.dumps(
        {
            "verdict": "verified",
            "state_id_number": state_id_number,
            "id_type": record["id_type"],
            "status": record["status"],
            "expires_on": record["expires_on"],
        }
    )


def main() -> None:
    log.info("Loaded %d state ID registry records", len(_REGISTRY))
    log.info(
        "State ID Verification MCP Server listening on http://%s:%s/mcp",
        CONFIG.host,
        CONFIG.port,
    )
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
