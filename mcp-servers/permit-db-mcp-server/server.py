"""Permit DB MCP Server — dedicated backend for the Permit & Licensing Agent (PLAN.md §6).

Exposes exactly the three tools PLAN.md calls for: permit_lookup, fee_schedule_read,
application_prefill. Both Permit & Licensing instances (Building Permits, Business Licenses)
share this same full-access dataset — there's no per-instance data partition here the way
there is for the Unified KB MCP Server, just API-key authentication.
"""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import Context, FastMCP

from config import Config
from seed_data import seed_all
from store import PermitDBStore

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("permit-db-mcp")

CONFIG = Config.from_env()
STORE = PermitDBStore(CONFIG.db_path, CONFIG.encryption_key)

mcp = FastMCP(
    "permit-db",
    instructions=(
        "Dedicated backend for Riverside County's Permit & Licensing Agent. Look up permit "
        "applications, read fee schedules, and pre-fill new applications. Every call requires "
        "a valid API key."
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


def _require_auth(ctx: Context) -> str:
    request = ctx.request_context.request
    api_key = _extract_api_key(request)
    caller = CONFIG.caller_label(api_key)
    if caller is None:
        raise ValueError(
            "Access denied: missing or unrecognized API key for the Permit DB MCP Server."
        )
    return caller


@mcp.tool()
def permit_lookup(permit_number: str, ctx: Context) -> str:
    """Look up a permit or business license application by its permit number.

    Returns status, applicant details, property address, valuation, and notes. Permit
    numbers look like BP-2026-00042 (building/ADU/solar/pool permits) or BL-2026-00012
    (business licenses / home occupation permits).
    """
    _require_auth(ctx)
    app = STORE.read_application(permit_number)
    if app is None:
        raise ValueError(f"No application found for permit number '{permit_number}'.")
    return json.dumps(
        {
            "permit_number": app.permit_number,
            "permit_type": app.permit_type,
            "status": app.status,
            "applicant_name": app.applicant_name,
            "applicant_email": app.applicant_email,
            "applicant_phone": app.applicant_phone,
            "property_address": app.property_address,
            "valuation": app.valuation,
            "submitted_at": app.submitted_at,
            "updated_at": app.updated_at,
            "notes": app.notes,
        }
    )


@mcp.tool()
def fee_schedule_read(permit_type: str, ctx: Context, valuation: float | None = None) -> str:
    """Read the fee schedule for a permit type, optionally estimating the total fee.

    Valid permit_type values: building_permit, adu_permit, solar_pv, pool_spa,
    business_license, home_occupation_permit. Pass a project valuation (in dollars) to get
    an estimated total fee; omit it to just see the base/plan-check fees and rate.
    """
    _require_auth(ctx)
    fee = STORE.read_fee_schedule(permit_type)
    if fee is None:
        available = ", ".join(STORE.list_permit_types())
        raise ValueError(f"Unknown permit_type '{permit_type}'. Available types: {available}.")
    estimated_total = STORE.estimate_fee(permit_type, valuation) if valuation else None
    return json.dumps(
        {
            "permit_type": fee.permit_type,
            "description": fee.description,
            "base_fee": fee.base_fee,
            "plan_check_fee": fee.plan_check_fee,
            "valuation_rate_per_1000": fee.valuation_rate_per_1000,
            "notes": fee.notes,
            "estimated_total_fee": estimated_total,
        }
    )


@mcp.tool()
def application_prefill(
    permit_type: str,
    applicant_name: str,
    applicant_email: str,
    applicant_phone: str,
    property_address: str,
    ctx: Context,
    valuation: float | None = None,
) -> str:
    """Create a new draft application pre-filled with the applicant's details.

    Generates a new permit number, creates a 'draft' status application, and returns an
    estimated fee based on the fee schedule for permit_type. Use fee_schedule_read first if
    you need to confirm the permit_type is valid before pre-filling.
    """
    _require_auth(ctx)
    if STORE.read_fee_schedule(permit_type) is None:
        available = ", ".join(STORE.list_permit_types())
        raise ValueError(f"Unknown permit_type '{permit_type}'. Available types: {available}.")
    import datetime

    year = datetime.datetime.now(datetime.timezone.utc).year
    permit_number = STORE.next_permit_number(permit_type, year)
    app = STORE.create_application(
        permit_number=permit_number,
        permit_type=permit_type,
        applicant_name=applicant_name,
        applicant_email=applicant_email,
        applicant_phone=applicant_phone,
        property_address=property_address,
        valuation=valuation,
    )
    estimated_total = STORE.estimate_fee(permit_type, valuation)
    return json.dumps(
        {
            "permit_number": app.permit_number,
            "permit_type": app.permit_type,
            "status": app.status,
            "applicant_name": app.applicant_name,
            "property_address": app.property_address,
            "valuation": app.valuation,
            "estimated_total_fee": estimated_total,
        }
    )


def main() -> None:
    seeded = seed_all(STORE)
    log.info("Seeded: %s", seeded)
    log.info("Permit DB MCP Server listening on http://%s:%s/mcp", CONFIG.host, CONFIG.port)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
