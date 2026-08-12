# State ID Verification MCP Server (external stand-in)

Simulates the third-party state ID/DMV verification service the Permit & Licensing Agent
checks before acting on an applicant's claimed identity, per [`PLAN.md`](../../PLAN.md) §5
("Dedicated Permit DB MCP + **external** State ID Verification MCP"). The county doesn't run
or own this system in real life — it just holds one integration credential. This server
stands in for that external system locally so the agent can be built and tested end-to-end
without a real state integration.

Deliberately the smallest of the three MCP servers in this repo: one tool, no partitioning,
read-only against a small static mock registry — there's nothing to write back to a state
database from the county's side.

## Tool

| Tool | Effect |
|---|---|
| `verify_state_id(state_id_number, full_name, date_of_birth)` | Verify a driver's license / state ID against the registry |

Verdicts: `verified` (active match), `name_or_dob_mismatch` (ID exists but details don't
match — possible fraud), `not_found` (no such ID), `inactive` (details match but the ID is
expired or suspended).

## Setup

```bash
cd /path/to/agora
source .venv/bin/activate
pip install -r mcp-servers/state-id-verification-mcp-server/requirements.txt
```

```bash
cd mcp-servers/state-id-verification-mcp-server
cp .env.example .env
```

The default `.env.example` already has a fictional integration credential
(`STATEID_API_KEY`) filled in — this is meant to represent the one credential the county was
issued by the state, so unlike the other two servers there's no key to generate.

## Run

```bash
source ../../.venv/bin/activate
set -a; source .env; set +a
python server.py
```

Serves streamable-HTTP MCP at `http://<host>:<port>/mcp` (default port `8102`).

## Testing

```bash
python test_client.py http://127.0.0.1:8102/mcp
```

Asserts: a correct name/DOB match against a known ID returns `verified`; a wrong name/DOB
against a real ID number is flagged `name_or_dob_mismatch` rather than passing; an unknown ID
number returns `not_found`; expired and suspended IDs are flagged `inactive` even when the
name/DOB match; and a missing or wrong integration credential is denied outright.
