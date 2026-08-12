# Case Management MCP Server

Dedicated backend MCP server for the Case Management Agent — the MCP-scoping centerpiece of
this demo, per [`PLAN.md`](../../PLAN.md) §7-8.

## Two independent boundaries, stacked

The server exposes **all seven** tools against the county case system, but enforces two
separate checks on every call:

1. **MCP tool scope.** The Case Management Agent's identity is granted exactly three tools —
   `case_search`, `case_read`, `case_notes_write`. Calling `case_status_update`,
   `citizen_profile_read`, `citizen_profile_write`, or `case_close` is denied with a
   `PermissionError` naming the scope violation, before it ever reaches the encrypted store.
2. **On-behalf-of identity.** Every call must also carry an opaque access token identifying
   *which caseworker* the agent is acting for. The server "introspects" that token (a local
   stand-in for RFC 7662 introspection against the county's real IDP) and restricts
   `case_search`/`case_read`/`case_notes_write` to that caseworker's own assigned cases. The
   agent's API key alone never grants access to every case — run the *same* instance as two
   different caseworkers and `case_search` returns two different case lists.

These are independent: a valid API key with no on-behalf-of token is denied; a valid
on-behalf-of token calling an out-of-scope tool is still denied.

## Tools

| Tool | In agent's scope? | Effect |
|---|---|---|
| `case_search(query?)` | Yes | List/search the on-behalf-of caseworker's own assigned cases |
| `case_read(case_id)` | Yes | Read a case's full details + notes (must be assigned to the caller) |
| `case_notes_write(case_id, note)` | Yes | Add a note to one of the caller's own cases |
| `case_status_update(case_id, new_status)` | **No** | Update a case's status |
| `citizen_profile_read(citizen_id)` | **No** | Read a citizen's full PII profile |
| `citizen_profile_write(citizen_id, ...)` | **No** | Update a citizen's profile |
| `case_close(case_id)` | **No** | Close a case |

## Storage & encryption

Embedded local SQLite (`data/case_mgmt.db`). Citizen PII (name, DOB, SSN last 4, address,
phone, email) and case note content are encrypted at rest with Fernet — the same field-level
simplification the other dedicated MCP servers use in place of SQLCipher.

## Setup

```bash
cd /path/to/agora
source .venv/bin/activate
pip install -r mcp-servers/case-management-mcp-server/requirements.txt
```

```bash
cd mcp-servers/case-management-mcp-server
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# paste the output as CASEMGMT_ENCRYPTION_KEY in .env
```

## Run

```bash
source ../../.venv/bin/activate
set -a; source .env; set +a
python server.py
```

Seeds 4 citizen profiles, 6 cases (3 assigned to each of 2 caseworkers), and 5 case notes on
every startup, then serves streamable-HTTP MCP at `http://<host>:<port>/mcp` (default port
`8103`).

## Credentials (fictional, for local dev/testing only)

| Credential | Value | Purpose |
|---|---|---|
| API key | `casemgmt_live_case-management-agent_6b8f31` | The Case Management Agent's MCP identity (3-of-7 scope) |
| On-behalf-of token | `obo_joan_ellis_4a7c9f` | Acting as caseworker Joan Ellis (cases 1001-1003) |
| On-behalf-of token | `obo_renee_alvarez_1e6b2d` | Acting as caseworker Renee Alvarez (cases 1004-1006) |

Pass the API key as `X-MCP-API-Key` (or `API-Key`/`Authorization: Bearer`) and the
on-behalf-of token as `X-OBO-Token` (or `X-On-Behalf-Of`).

## Testing

```bash
python test_client.py http://127.0.0.1:8103/mcp
```

Asserts: Joan and Renee see disjoint case lists from the same API key; each caseworker can
read/note their own cases but is denied on the other's; all four out-of-scope tools are
denied with a message naming the MCP scope violation; and a missing/invalid API key or
on-behalf-of token is denied even when the other credential is valid.
