# Permit DB MCP Server

Dedicated backend MCP server for the Permit & Licensing Agent, per [`PLAN.md`](../../PLAN.md)
§6. Unlike the Unified KB MCP Server, this one is **not** namespace-partitioned — both Permit
& Licensing instances (Building Permits, Business Licenses) share the same full-access permit
and fee-schedule data. API keys here are authentication only, not a data boundary.

## Tools

| Tool | Effect |
|---|---|
| `permit_lookup(permit_number)` | Look up a permit/business-license application by number |
| `fee_schedule_read(permit_type, valuation?)` | Read a permit type's fee schedule, optionally with an estimated total fee |
| `application_prefill(permit_type, applicant_name, applicant_email, applicant_phone, property_address, valuation?)` | Create a new draft application, auto-assigning a permit number |

Permit types: `building_permit`, `adu_permit`, `solar_pv`, `pool_spa`, `business_license`,
`home_occupation_permit`.

## Storage & encryption

Embedded local SQLite (`data/permit_db.db`). Applicant PII (name, email, phone) is encrypted
at rest with [Fernet](https://cryptography.io/en/latest/fernet/) — the same field-level
simplification the Unified KB MCP Server uses in place of SQLCipher. There's no working
SQLCipher wheel (`sqlcipher3-binary`, `pysqlcipher3`) for this environment, and building
`libsqlcipher` from source is out of scope for a demo; Fernet gets the same at-rest guarantee
for the sensitive columns without a fragile native dependency. Swapping in real SQLCipher
later wouldn't change the tool contract above.

## Setup

Uses the shared root virtualenv:

```bash
cd /path/to/agora
source .venv/bin/activate
pip install -r mcp-servers/permit-db-mcp-server/requirements.txt
```

```bash
cd mcp-servers/permit-db-mcp-server
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# paste the output as PERMITDB_ENCRYPTION_KEY in .env
```

## Run

```bash
source ../../.venv/bin/activate
set -a; source .env; set +a
python server.py
```

Seeds 6 fee schedules and 6 permit applications on every startup (idempotent upsert) and
serves streamable-HTTP MCP at `http://<host>:<port>/mcp` (default port `8101`).

## API keys (fictional, for local dev/testing only)

| Instance | API key |
|---|---|
| Building Permits | `permitdb_live_building-permits_7c1a4e` |
| Business Licenses | `permitdb_live_business-licenses_2f9b6d` |

Both keys have identical, full access — there's only one dataset behind this server. Pass
either as `X-MCP-API-Key`, `API-Key`, or `Authorization: Bearer <key>`.

## Testing

```bash
python test_client.py http://127.0.0.1:8101/mcp
```

Asserts: seeded applications are readable and correctly decrypted, both API keys can read
the same data (no partitioning), unknown permit numbers/types are denied rather than
returning empty, `application_prefill` creates a draft that's immediately readable, fee
estimates compute correctly from the schedule, and invalid/missing API keys are denied.
