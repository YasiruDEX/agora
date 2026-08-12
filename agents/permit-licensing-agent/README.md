# Permit & Licensing Agent

Python/LangChain agent that guides Riverside County residents through permit and business
license questions, per [`PLAN.md`](../../PLAN.md) §5/§6.

**One image, one prompt, 2 running instances** — Building Permits and Business Licenses. Both
instances talk to the same two MCP servers:

- [Permit DB MCP Server](../../mcp-servers/permit-db-mcp-server) — dedicated, full-access
  backend for permit/license lookups, fee schedules, and application pre-fill. Not
  namespace-partitioned like the Unified KB server — both instances see the same data, since
  there's only one Permits & Licensing department.
- [State ID Verification MCP Server](../../mcp-servers/state-id-verification-mcp-server) — an
  external stand-in service the agent checks before creating a new application on someone's
  claimed identity.

## How it's wired

```
Resident → POST /chat → LangGraph ReAct agent → permit_lookup / fee_schedule_read / application_prefill
                                     │                          (Permit DB MCP)
                                     └──────────────────→ verify_state_id
                                                           (State ID Verification MCP, external)
```

- **Tool binding**: `mcp_tools.py` loads both MCP servers' tools in one
  `MultiServerMCPClient`, sending both `X-MCP-API-Key` and `API-Key` headers (same
  dual-header trick as the Citizen Inquiry Agent, for direct-vs-proxied compatibility).
- **Identity check before write**: the system prompt in `agent.py` requires calling
  `verify_state_id` before `application_prefill` — an unverified name/DOB/ID combination
  blocks the application rather than being silently accepted.
- **Grounded fees**: fee figures always come from `fee_schedule_read`, never invented, and
  are always presented as estimates.

## Setup

Uses the shared root virtualenv (`../../.venv`):

```bash
cd /path/to/agora
source .venv/bin/activate
pip install -r agents/permit-licensing-agent/requirements.txt
```

Start both MCP servers first (see their READMEs):
- Permit DB MCP Server on `http://127.0.0.1:8101/mcp`
- State ID Verification MCP Server on `http://127.0.0.1:8102/mcp`

## Running an instance

```bash
cd agents/permit-licensing-agent
ENV_FILE=.env.building-permits  python main.py   # port 8011
ENV_FILE=.env.business-licenses python main.py   # port 8012
```

| Env var | Purpose |
|---|---|
| `COUNTY_NAME` | Branding in the system prompt |
| `PERMIT_TYPE_FOCUS` | Branding/tone only — both instances have identical data access |
| `PERMITDB_MCP_SERVER_URL` / `PERMITDB_MCP_API_KEY` | Permit DB MCP server connection |
| `STATEID_MCP_SERVER_URL` / `STATEID_MCP_API_KEY` | State ID Verification MCP server connection |
| `TONE`, `ADDITIONAL_GUIDANCE` | Per-instance prompt tuning |
| `PORT` | Local port for this instance |
| `OPENAI_API_KEY` | Direct OpenAI (dev/local) |
| `USE_LLM_PROVIDER`, `LLM_PROVIDER_URL`, `LLM_PROVIDER_KEY` | Route through the AM LLM Proxy instead (PLAN.md §9) |

## Testing

Verified end-to-end in the codebase (no Agent Manager involved) with both MCP servers and
the Building Permits instance running locally:

```bash
curl -s http://127.0.0.1:8011/health

curl -s -X POST http://127.0.0.1:8011/chat -H 'Content-Type: application/json' \
  -d '{"message": "What would it cost to build a 650 sqft ADU worth about $90,000?"}'

curl -s -X POST http://127.0.0.1:8011/chat -H 'Content-Type: application/json' \
  -d '{"message": "Can you check the status of permit BP-2026-00042?"}'

curl -s -X POST http://127.0.0.1:8011/chat -H 'Content-Type: application/json' \
  -d '{"message": "I'\''m Maria Gutierrez, DOB 1985-03-14, driver'\''s license CA-DL-D1234567. I want to start a new ADU permit application at 18420 Vista Del Sol Dr, email maria.gutierrez@example.com, phone 951-555-0142."}'
```

Confirmed: the fee estimate matches the fee schedule's formula, the permit lookup returns the
seeded application's real status, and the new-application request correctly calls
`verify_state_id` before `application_prefill` and only proceeds because the identity matched.
