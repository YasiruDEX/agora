# Citizen Inquiry Agent

Python/LangChain agent that answers Riverside County resident questions from a
department-scoped knowledge base, per [`PLAN.md`](../../PLAN.md) §5/§6.

**One image, one prompt, 5 running instances** — Social Services, Permits & Licensing, Tax &
Revenue, Records & Compliance, Contact Center. Every instance calls the same
[Unified KB MCP Server](../../mcp-servers/unified-kb-mcp-server) — fronted by an MCP proxy —
at the same `MCP_SERVER_URL`. Namespace resolution still happens on the MCP side, unchanged;
what differs per instance is the OAuth2 AgentID service-account credentials Agent Manager
injects, which the proxy maps to one department's namespace. This agent never decides which
namespace it can see — it just gets back whatever the four `kb_*` tools return for its token.

Published to the catalog as [`catalog/citizen-inquiry-agent.yaml`](../../catalog/citizen-inquiry-agent.yaml)
— the demo's stand-in for `amp:agent-kind:create` (there's no live Agent Manager control
plane here, so this manifest is the record of what got "published").

## How it's wired

```
Resident → POST /chat → LangGraph ReAct agent → kb_search / kb_read / kb_write / kb_list_sources
                                                        │
                                                        ▼ (OAuth2 client-credentials, RFC 8707 resource)
                                              MCP proxy → Unified KB MCP Server
                                       (namespace resolved from whatever credential the proxy forwards)
```

- **Auth**: `mcp_tools.py` mints an OAuth2 access token via client-credentials grant against
  `AMP_AGENTID_TOKEN_ENDPOINT`, using the `AMP_AGENTID_CLIENT_ID`/`AMP_AGENTID_CLIENT_SECRET`
  Agent Manager injects, scoped to `MCP_SERVER_URL` via the `resource` parameter (RFC 8707) —
  the token is bound to this specific MCP endpoint, not reusable elsewhere. That token is then
  sent as `Authorization: Bearer <token>` on every MCP call. The token is fetched once at
  startup, alongside loading the 4 KB tools via `langchain-mcp-adapters`'
  `MultiServerMCPClient(streamable_http)`.
- **Grounding**: the system prompt in `agent.py` requires the model to search the KB before
  answering, cite the source article, and say "I don't have that information" rather than
  invent policy/fee/deadline details — the KB is the only source of truth.
- **Scope containment**: if a resident (or a malicious prompt) asks about another
  department's services or tries to `kb_read` another namespace's `doc_id` directly, the MCP
  server denies it — not this agent's judgment. See the MCP server's own isolation tests for
  the enforcement layer; this agent's system prompt is a second, softer line of defense (say
  "that's not my department" instead of guessing), not the actual boundary.

## Deploy in Agent Manager

This agent kind is instantiated 5 times — once per department — from the *same* App Path and
image, differing only in the environment variables below (PLAN.md §5/§6). Repeat Steps 2-4
once per department to stand up all 5 instances.

### Step 1: Access Agent Manager

1. Navigate to the project for **Riverside County — Department of Citizen Services**
2. Select **Platform-Hosted Agent** Card
3. Pick **Source Code** as the source type of the agent

### Step 2: Configure Agent Details

| Field | Value |
| --- | --- |
| **Display Name** | `Citizen Inquiry Agent — <Department>` (e.g. `Citizen Inquiry Agent — Social Services`) |
| **Description** | `Answers resident questions from the department's namespace-scoped knowledge base` |
| **GitHub Repository** | this repository |
| **Branch** | `main` |
| **App Path** | `agents/citizen-inquiry-agent` |
| **Language** | `Python` |
| **Language Version** | `3.11` |
| **Start Command** | `python main.py` |
| **Port** | `8000` |

### Step 3: Select Agent Interface

- Choose **"Chat Agent"** as the agent interface type (standard `POST /chat` on port `8000`,
  contract documented in [`openapi.yaml`](openapi.yaml))

### Step 4: Configure Environment Variables

One department's values per instance — see the table below and the matching
`.env.<department>` file for the exact values used in this demo:

```env
COUNTY_NAME=Riverside County
DEPARTMENT_NAME=<Social Services|Permits & Licensing|Tax & Revenue|Records & Compliance|Contact Center>
MCP_SERVER_URL=<Unified KB MCP proxy URL — same for every instance>
AMP_AGENTID_CLIENT_ID=<this instance's AgentID service-account client ID>
AMP_AGENTID_CLIENT_SECRET=<this instance's AgentID service-account client secret>
AMP_AGENTID_TOKEN_ENDPOINT=<AgentID OAuth2 token endpoint>
AMP_AGENTID_SCOPES=<scopes requested for this instance's token>
OPENAI_API_KEY=<your-openai-api-key>
```

### Step 5: Deploy

Review and click **Deploy**. Marcus/Priya (Department Developer) can push to Dev/Staging;
only Dana (Platform Admin) can promote to Production (PLAN.md §3).

## Setup

Uses the shared root virtualenv (`../../.venv`):

```bash
cd /path/to/agora
source .venv/bin/activate
pip install -r agents/citizen-inquiry-agent/requirements.txt
```

Make sure the Unified KB MCP Server is running first (see its README) — default
`http://127.0.0.1:8100/mcp`.

## Running an instance

Each department instance is told apart by which `.env` file it loads — this mirrors Agent
Manager injecting different env vars per deployed instance, just done locally with files
instead of the control plane:

```bash
cd agents/citizen-inquiry-agent
ENV_FILE=.env.social-services   python main.py   # port 8001
ENV_FILE=.env.permits-licensing python main.py   # port 8002
ENV_FILE=.env.tax-revenue       python main.py   # port 8003
ENV_FILE=.env.records-compliance python main.py  # port 8004
ENV_FILE=.env.contact-center    python main.py   # port 8005
```

With no `ENV_FILE` set, it falls back to `.env` (copy `.env.example` and fill in your own
`OPENAI_API_KEY` to use that path).

| Env var | Purpose |
|---|---|
| `COUNTY_NAME` | Branding in the system prompt (`Riverside County`) |
| `DEPARTMENT_NAME` | Branding/tone only — **not** a security boundary |
| `MCP_SERVER_URL` | Unified KB MCP proxy endpoint (same for every instance) — also used as the OAuth2 resource indicator |
| `AMP_AGENTID_CLIENT_ID`, `AMP_AGENTID_CLIENT_SECRET` | This instance's AgentID service-account credentials for the OAuth2 client-credentials grant |
| `AMP_AGENTID_TOKEN_ENDPOINT` | Where to request the access token |
| `AMP_AGENTID_SCOPES` | Scopes requested on the token |
| `TONE`, `ADDITIONAL_GUIDANCE` | Per-department prompt tuning |
| `PORT` | Local port for this instance |
| `OPENAI_API_KEY` | Direct OpenAI (dev/local) |
| `USE_LLM_PROVIDER`, `LLM_PROVIDER_URL`, `LLM_PROVIDER_KEY` | Route through the AM LLM Proxy instead (PLAN.md §9) |

## Testing

```bash
curl -s http://127.0.0.1:8001/health

curl -s -X POST http://127.0.0.1:8001/chat -H 'Content-Type: application/json' \
  -d '{"message": "How much do I need to qualify for CalFresh with a household of 4?"}'
```

> **Note:** the isolation/grounding behavior below was verified against the old static
> `X-MCP-API-Key` header scheme. The code now speaks OAuth2 to an MCP proxy instead (see
> "How it's wired" above) — the MCP server side and its namespace enforcement are unchanged,
> but re-verifying this agent end-to-end requires a real OAuth2 token endpoint/proxy, which
> isn't available locally. Retest once pointed at the actual proxy.

Previously verified end-to-end with two instances running side by side (pre-OAuth2):
- Social Services (8001) correctly answers CalFresh questions with a citation to the source
  article, and cannot be prompt-injected into reading a Tax & Revenue `doc_id` (`tr-001`) —
  the MCP server returns "no article found," not the other department's content.
- Tax & Revenue (8003) correctly declines the same CalFresh question ("I don't have
  information regarding CalFresh...") while answering its own property-tax questions fully —
  same agent code, same tool names, different data reachable, purely from the API key.

This is the demo beat from PLAN.md §13.3: same tool, five departments, five API keys — the
KB server never changes, only the identity does.
