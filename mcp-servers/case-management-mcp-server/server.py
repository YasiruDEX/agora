"""Case Management MCP Server — the MCP-scoping centerpiece (PLAN.md §7-8).

Exposes all seven tools against the county case system, but the Case Management Agent's
identity is only scoped into three: case_search, case_read, case_notes_write. Calling any of
the other four (case_status_update, citizen_profile_read, citizen_profile_write, case_close)
is denied by MCP scope enforcement before it reaches the encrypted store — a clean policy
rejection, not a crash or a hallucinated success.

On top of that, every call must carry an on-behalf-of opaque token identifying which
caseworker the agent is acting for (RFC 7662-style introspection stand-in). case_search,
case_read, and case_notes_write are all filtered/restricted to that caseworker's own assigned
cases — the agent's API key alone never grants access to every case in the system.
"""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import Context, FastMCP

from config import ALL_TOOLS, SCOPED_TOOLS, Config
from seed_data import seed_all
from store import CaseManagementStore

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("case-mgmt-mcp")

CONFIG = Config.from_env()
STORE = CaseManagementStore(CONFIG.db_path, CONFIG.encryption_key)

mcp = FastMCP(
    "case-management",
    instructions=(
        "Dedicated backend for Riverside County's Case Management Agent. The calling "
        "identity is scoped into exactly three of these seven tools (case_search, "
        "case_read, case_notes_write) — the rest are denied by MCP scope enforcement. Every "
        "call also requires an on-behalf-of token identifying the caseworker; results are "
        "restricted to that caseworker's own assigned cases."
    ),
    host=CONFIG.host,
    port=CONFIG.port,
)


def _extract_header(request, *names: str) -> str | None:
    if request is None:
        return None
    for name in names:
        val = request.headers.get(name)
        if val:
            return val
    return None


def _authorize(ctx: Context, tool_name: str) -> dict[str, str]:
    """Enforce both boundaries. Returns the introspected caseworker identity on success."""
    request = ctx.request_context.request
    api_key = _extract_header(request, "x-mcp-api-key", "api-key")
    if api_key != CONFIG.api_key:
        raise ValueError(
            "Access denied: missing or invalid API key for the Case Management MCP Server."
        )

    if tool_name not in ALL_TOOLS:
        raise ValueError(f"Unknown tool '{tool_name}'.")
    if tool_name not in SCOPED_TOOLS:
        log.warning("MCP SCOPE DENIAL: tool=%s is outside the agent's granted scope %s", tool_name, sorted(SCOPED_TOOLS))
        raise PermissionError(
            f"MCP scope violation: '{tool_name}' is not in this identity's granted tool "
            f"scope ({', '.join(sorted(SCOPED_TOOLS))}). Denied before reaching the store."
        )

    obo_token = _extract_header(request, "x-obo-token", "x-on-behalf-of")
    caseworker = CONFIG.introspect(obo_token)
    if caseworker is None:
        raise ValueError(
            "Access denied: missing or inactive on-behalf-of token. This MCP server requires "
            "a valid X-OBO-Token identifying the caseworker, on top of the API key."
        )
    return caseworker


def _require_own_case(caseworker: dict[str, str], case_id: str):
    case = STORE.read_case(case_id)
    if case is None:
        raise ValueError(f"No case found for case_id '{case_id}'.")
    if case.assigned_caseworker_id != caseworker["caseworker_id"]:
        log.warning(
            "CASE OWNERSHIP DENIAL: caseworker=%s attempted case=%s assigned to=%s",
            caseworker["caseworker_id"],
            case_id,
            case.assigned_caseworker_id,
        )
        raise PermissionError(
            f"Access denied: case '{case_id}' is not assigned to {caseworker['name']}."
        )
    return case


# -- the 3 tools the Case Management Agent is actually scoped into --------------------------


@mcp.tool()
def case_search(ctx: Context, query: str = "") -> str:
    """Search the on-behalf-of caseworker's own assigned cases.

    Pass an empty query to list all of the caseworker's cases, or a keyword to filter by
    case type, status, or summary text. Never returns another caseworker's cases.
    """
    caseworker = _authorize(ctx, "case_search")
    cases = STORE.search_cases(caseworker["caseworker_id"], query)
    return json.dumps(
        {
            "caseworker": caseworker["name"],
            "query": query,
            "results": [
                {
                    "case_id": c.case_id,
                    "citizen_id": c.citizen_id,
                    "case_type": c.case_type,
                    "status": c.status,
                    "summary": c.summary,
                    "updated_at": c.updated_at,
                }
                for c in cases
            ],
        }
    )


@mcp.tool()
def case_read(case_id: str, ctx: Context) -> str:
    """Read full details of a case, including its notes.

    Only cases assigned to the on-behalf-of caseworker are readable — a case_id belonging to
    another caseworker is denied, not just filtered out of search.
    """
    caseworker = _authorize(ctx, "case_read")
    case = _require_own_case(caseworker, case_id)
    notes = STORE.list_notes(case_id)
    return json.dumps(
        {
            "case_id": case.case_id,
            "citizen_id": case.citizen_id,
            "case_type": case.case_type,
            "status": case.status,
            "summary": case.summary,
            "opened_at": case.opened_at,
            "updated_at": case.updated_at,
            "notes": [
                {"author": n.author, "content": n.content, "created_at": n.created_at} for n in notes
            ],
        }
    )


@mcp.tool()
def case_notes_write(case_id: str, note: str, ctx: Context) -> str:
    """Add a note to one of the on-behalf-of caseworker's own assigned cases."""
    caseworker = _authorize(ctx, "case_notes_write")
    _require_own_case(caseworker, case_id)
    created = STORE.add_note(case_id=case_id, author=caseworker["name"], content=note)
    return json.dumps(
        {
            "case_id": created.case_id,
            "author": created.author,
            "content": created.content,
            "created_at": created.created_at,
            "status": "written",
        }
    )


# -- the 4 tools outside the Case Management Agent's granted scope -----------------------
# Implemented for completeness (this server also has to exist for a hypothetical admin
# tool/UI with a broader scope) but any call through the Case Management Agent's identity
# is denied in _authorize() before any of this code runs.


@mcp.tool()
def case_status_update(case_id: str, new_status: str, ctx: Context) -> str:
    """Update a case's status. OUTSIDE the Case Management Agent's granted MCP scope."""
    caseworker = _authorize(ctx, "case_status_update")
    _require_own_case(caseworker, case_id)
    updated = STORE.update_status(case_id, new_status)
    return json.dumps({"case_id": updated.case_id, "status": updated.status})


@mcp.tool()
def citizen_profile_read(citizen_id: str, ctx: Context) -> str:
    """Read a citizen's full profile (PII). OUTSIDE the Case Management Agent's granted MCP scope."""
    _authorize(ctx, "citizen_profile_read")
    profile = STORE.read_citizen(citizen_id)
    if profile is None:
        raise ValueError(f"No citizen profile found for citizen_id '{citizen_id}'.")
    return json.dumps(
        {
            "citizen_id": profile.citizen_id,
            "full_name": profile.full_name,
            "date_of_birth": profile.date_of_birth,
            "ssn_last4": profile.ssn_last4,
            "address": profile.address,
            "phone": profile.phone,
            "email": profile.email,
            "household_size": profile.household_size,
            "notes": profile.notes,
        }
    )


@mcp.tool()
def citizen_profile_write(
    citizen_id: str,
    ctx: Context,
    full_name: str | None = None,
    address: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    notes: str | None = None,
) -> str:
    """Update a citizen's profile fields. OUTSIDE the Case Management Agent's granted MCP scope."""
    _authorize(ctx, "citizen_profile_write")
    updates = {
        k: v
        for k, v in {
            "full_name": full_name,
            "address": address,
            "phone": phone,
            "email": email,
            "notes": notes,
        }.items()
        if v is not None
    }
    updated = STORE.update_citizen_fields(citizen_id, **updates)
    if updated is None:
        raise ValueError(f"No citizen profile found for citizen_id '{citizen_id}'.")
    return json.dumps({"citizen_id": updated.citizen_id, "status": "updated"})


@mcp.tool()
def case_close(case_id: str, ctx: Context) -> str:
    """Close a case. OUTSIDE the Case Management Agent's granted MCP scope."""
    caseworker = _authorize(ctx, "case_close")
    _require_own_case(caseworker, case_id)
    closed = STORE.close_case(case_id)
    return json.dumps({"case_id": closed.case_id, "status": closed.status})


def main() -> None:
    seeded = seed_all(STORE)
    log.info("Seeded: %s", seeded)
    log.info(
        "Case Management MCP Server listening on http://%s:%s/mcp (scoped tools=%s of %s)",
        CONFIG.host,
        CONFIG.port,
        sorted(SCOPED_TOOLS),
        sorted(ALL_TOOLS),
    )
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
