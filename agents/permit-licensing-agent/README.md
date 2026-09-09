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
                                     │                          (Permit DB MCP, via proxy)
                                     └──────────────────→ verify_state_id
                                                           (State ID Verification MCP, via proxy)
```

- **Auth**: `mcp_tools.py` mints OAuth2 access tokens via client-credentials grant against
  `AMP_AGENTID_TOKEN_ENDPOINT`, using the single `AMP_AGENTID_CLIENT_ID`/`CLIENT_SECRET`
  Agent Manager injects for this instance. One identity, two MCP resources — a separate token
  is requested per server (the `resource` parameter, RFC 8707, differs between
  `PERMITDB_MCP_SERVER_URL` and `STATEID_MCP_SERVER_URL`), each cached and refreshed
  independently ahead of its own expiry. Both are sent as `Authorization: Bearer <token>`.
  Tools are (re)loaded fresh on every `/chat` request rather than once at startup — see
  `app.py`'s docstring for why that matters (a token baked in at startup goes stale).
- **Resilience**: a tool call that fails at the transport level (e.g. the gateway rejecting a
  request outside this identity's granted scope) gets retried a few times before the resident
  ever sees anything go wrong; if it's still failing after retries, they get a plain-language
  "I don't have access to that right now" instead of a raw error.
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
| `PERMITDB_MCP_SERVER_URL` | Permit DB MCP proxy endpoint — also the OAuth2 resource indicator for that token |
| `STATEID_MCP_SERVER_URL` | State ID Verification MCP proxy endpoint — same, its own resource indicator |
| `AMP_AGENTID_CLIENT_ID`, `AMP_AGENTID_CLIENT_SECRET` | This instance's AgentID service-account credentials (shared across both MCP resources) |
| `AMP_AGENTID_TOKEN_ENDPOINT` | Where to request access tokens |
| `AMP_AGENTID_SCOPES` | Scopes requested on each token |
| `TONE`, `ADDITIONAL_GUIDANCE` | Per-instance prompt tuning |
| `PORT` | Local port for this instance |
| `OPENAI_API_KEY` | Direct OpenAI (dev/local) |
| `USE_LLM_PROVIDER`, `LLM_PROVIDER_URL`, `LLM_PROVIDER_KEY` | Route through the AM LLM Proxy instead (PLAN.md §9) |

## Testing

**OAuth2 flow verified end-to-end** against both real (unchanged) MCP servers, using a
throwaway local stand-in for the AgentID token endpoint that issues a distinct token per
`resource` requested — confirmed both `PERMITDB_MCP_SERVER_URL` and `STATEID_MCP_SERVER_URL`
each got their own correct token, and both a fee-estimate question (Permit DB only) and a new
application (which requires `verify_state_id` against State ID Verification, then
`application_prefill` against Permit DB) worked correctly end-to-end.

Previously verified end-to-end in the codebase (no Agent Manager involved, pre-OAuth2) with
both MCP servers and the Building Permits instance running locally:

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
