# Agora

> **Agora** — the civic gathering place and marketplace. A pre-configured, pre-seeded
> demonstration of **WSO2 Agent Manager** where a fictional county government's departments
> browse a catalog of pre-built agents and staff their own **instantiable workforce**.

This repo is where we iteratively design and build the demo scenario. It starts as a plan and
grows into the actual configuration, seed data, and supporting services as we implement it.

## The story in one line

A small central AI Platform Team publishes agent *kinds* to the catalog; departments across
**Riverside County — Department of Citizen Services** instantiate their own, under strict
identity and governance controls (on-behalf-of access, identity-aware MCP governance, on-prem
models for PII, full auditing).

## Repo layout

```
agora/
├── README.md                    # you are here
├── PLAN.md                      # the full demo blueprint — the working source of truth
└── docs/
    └── demo-blueprint.html      # visual (civic-report) version of the plan
```

## Status

🌱 **Planning.** The scenario is defined in [`PLAN.md`](./PLAN.md). Nothing is built yet.

## Roadmap (rough)

- [x] Define the demo scenario & story (see `PLAN.md`)
- [ ] Resolve the open questions at the bottom of `PLAN.md` (runtime, mocked vs. real backends, seed-data approach)
- [ ] Model the org: departments, users, roles, environments
- [ ] Build the catalog agent kinds
- [ ] Wire up MCP backends + governance policies
- [ ] Configure identity flows (Agent IDs, OAuth2 on-behalf-of, IDP)
- [ ] Register LLM providers + guardrails
- [ ] Instantiate the workforce (~10 instances)
- [ ] Generate ~6 months of seed traces & evaluations
- [ ] Rehearse the demo narrative end-to-end

## How we work in here

`PLAN.md` is the source of truth for the *what*. As we implement, we add the *how* alongside it
and keep the plan in sync. Commit iteratively.

---

# Implementation Reference

The sections above are the original demo plan. Everything below documents what has actually been
built so far: a multi-departmental government service portal (`gov.lk` / `gic.gov.lk`) backed by
independent, domain-scoped LangGraph agents and Model Context Protocol (MCP) tool servers, plus a
React frontend. This is a demo/reference build, not the official gov.lk website.

## System Architecture

```
                                   ┌────────────────────────────┐
                                   │   frontend/ (React + Vite)  │
                                   │  Header · Nav · HeroCarousel│
                                   │  Department pages · Chat UI │
                                   └──────────────┬─────────────┘
                                                  │ POST /chat (VITE_USE_MOCK_AGENTS=false)
                                                  │ or src/mock/agentMocks.js (default)
                    ┌─────────────────────────────┼──────────────────────────────────┐
                    │                             │                                  │
                    ▼                             ▼                                  ▼
         ┌────────────────────┐        ┌───────────────────────┐        ┌───────────────────────┐
         │ Central Portal      │        │ Citizen Inquiry Agent │        │ Benefits Eligibility   │
         │ Agent :8007         │        │ :8001 (Contact Center)│        │ Agent :8000 (Soc. Svc) │
         │ cloud-standard      │        │ cloud-standard        │        │ cloud-standard         │
         └─────────┬───────────┘        └──────────┬────────────┘        └──────────┬─────────────┘
                   │                                │  ▲ consult_citizen_inquiry_agent (A2A/HTTP)
                   │                                │  │  from every other citizen-facing agent
                   ▼                                │  │
        ┌───────────────────────┐                   │  │
        │ pinecone-kb MCP        │◄──────────────────┘  │
        │ search_knowledge_base  │                       │
        │ (5 namespaces)         │                       │
        └───────────────────────┘                       │
                                                          │
   ┌───────────────────┬────────────────────┬────────────┴───────┬───────────────────────┐
   ▼                   ▼                    ▼                    ▼                       ▼
┌───────────────┐ ┌───────────────┐  ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│ Permit &      │ │ Tax &         │  │ Case Management    │ │ Records / FOIA     │ │ sqlite-db-mcp      │
│ Licensing     │ │ Assessment    │  │ Agent :8005         │ │ Agent :8006        │ │ (social_services.db)│
│ :8002 / :8003 │ │ Agent :8004   │  │ on-prem (vLLM)      │ │ cloud-standard     │ └───────────────────┘
│ cloud-standard│ │ cloud-standard│  └──────────┬──────────┘ └──────────┬─────────┘
└──────┬────────┘ └──────┬────────┘             │                       │
       ▼                 ▼                      ▼                       ▼
┌──────────────┐  ┌───────────────┐     ┌──────────────────┐   ┌──────────────────────┐
│ permit-db-mcp │  │ tax-db-mcp    │     │ case-db-mcp       │   │ records-db-mcp        │
│ (building_    │  │ (tax_revenue  │     │ (case_management  │   │ (records_compliance   │
│  permits.db / │  │  .db)         │     │  .db)             │   │  .db) + redact_pii_text│
│  business_    │  ├───────────────┤     └──────────────────┘   └──────────────────────┘
│  licenses.db) │  │ payment-mcp   │
└──────────────┘  │ (same tax db) │
                   └───────────────┘
```

All MCP servers are local, stdio-transport Python processes (`.venv/bin/python
mcp_servers/<name>/server.py`), launched by each agent's LangGraph tool-binding step — there is
no separate MCP gateway process to run.

## Agent Catalog

| Agent (codebase)                             | Port(s)     | Department / Instance                          | `targetLlmTier` (provider / model)                          | Primary MCP tools                                                                 |
| --------------------------------------------- | ----------- | ----------------------------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `central_portal_agent`                        | 8007        | Government Information Center (GIC 1919)        | `cloud-standard` (`azure-openai-gov` / `gpt-4o`)               | `pinecone-kb.search_knowledge_base` fanned out across all 5 KB namespaces          |
| `citizen_inquiry_agent`                       | 8001        | Contact Center (generic per-department template) | `cloud-standard` (`azure-openai-gov` / `gpt-4o`)               | `pinecone-kb.search_knowledge_base` scoped to one `KB_NAMESPACE`                   |
| `benefits_eligibility_agent`                  | 8000        | Department of Social Services                    | `cloud-standard` (`azure-openai-gov` / `gpt-4o`)               | `pinecone-kb.search_knowledge_base`, `sqlite-db-mcp` CRUD on `citizens` / `welfare_applications` |
| `permit_licensing_agent` (Building Permits)   | 8002        | Permits & Licensing — Building Permits Division  | `cloud-standard` (`azure-openai-gov` / `gpt-4o`)               | `pinecone-kb.search_knowledge_base`, `permit-db-mcp` CRUD (`PERMIT_DB_PATH=data/building_permits.db`) |
| `permit_licensing_agent` (Business Licenses)  | 8003        | Permits & Licensing — Business & Trade Licenses  | `cloud-standard` (`azure-openai-gov` / `gpt-4o`)               | `pinecone-kb.search_knowledge_base`, `permit-db-mcp` CRUD (`PERMIT_DB_PATH=data/business_licenses.db`) |
| `tax_assistance_agent`                        | 8004        | Tax & Revenue Department                         | `cloud-standard` (`azure-openai-gov` / `gpt-4o`)               | `pinecone-kb.search_knowledge_base`, `tax-db-mcp` CRUD, `payment-mcp` (`create_payment_link`, `verify_and_settle_payment`) |
| `case_management_agent`                       | 8005        | Department of Social Services (Caseworker portal)| `on-prem` (`onprem-vllm` / `llama-3-70b-instruct`)             | `pinecone-kb.search_knowledge_base`, `case-db-mcp` CRUD wrapped in OBO-scoped tools |
| `records_foia_agent`                          | 8006        | Department of Records & Compliance               | `cloud-standard` (`azure-openai-gov` / `gpt-4o`)               | `pinecone-kb.search_knowledge_base`, `records-db-mcp` CRUD + `redact_pii_text`     |

Every citizen-facing agent above (all except `central_portal_agent`) also carries a
`consult_citizen_inquiry_agent` agent-to-agent tool that forwards out-of-scope questions to
`INQUIRY_AGENT_URL` (default `http://localhost:8001/chat`) over plain HTTP.

`benefits_eligibility_agent` and `tax_assistance_agent` handle income, age, and property data
but currently default to `cloud-standard` like the rest of the fleet — `case_management_agent`
is the only agent configured for the `on-prem` tier out of the box. Per-agent tiering is set in
each `manifest.yaml`'s `spec.targetLlmTier` and the `LLM_PROVIDER_KEY` / `LLM_MODEL_NAME` /
`LLM_BASE_URL` parameters, so routing any agent to an on-prem vLLM endpoint is a config change,
not a code change.

`permit_licensing_agent` is a single codebase run as two independent instances via
`AGENT_ENV_FILE` (`.env.building_permits` / `.env.business_licenses`), each with its own port
and its own isolated SQLite file — see [`scripts/test_multi_instance_permits.py`](scripts/test_multi_instance_permits.py)
for an automated check of that isolation.

## Model Context Protocol (MCP) Infrastructure

All servers live under `mcp_servers/`, run as local `stdio` Python processes, and are declared
per-agent in `agents/<agent>/manifest.yaml`.

| Server (`config.json` key) | File                                       | Backing store                                    | Tools |
| --------------------------- | ------------------------------------------- | ------------------------------------------------- | ----- |
| `pinecone-kb`               | `mcp_servers/pinecone_kb_mcp/server.py`      | Pinecone index (`PINECONE_INDEX_NAME`)             | `search_knowledge_base(namespace, query, top_k=5)` — namespaces: `tax-revenue`, `social-services`, `permits-licensing`, `records-compliance`, `health-environment` |
| `sqlite-db-mcp`              | `mcp_servers/sqlite_db_mcp/server.py`        | `data/social_services.db` (`citizens`, `welfare_applications`) | `db_create_record`, `db_read_record`, `db_update_record`, `db_delete_record` |
| `case-db-mcp`                | `mcp_servers/case_db_mcp/server.py`          | `data/case_management.db` (`cases`, `case_notes`) | `db_read_record`, `db_create_record`, `db_update_record` (no delete — raw tools are wrapped by `graph.py` into OBO-scoped tools before the LLM ever sees them) |
| `permit-db-mcp`              | `mcp_servers/permit_db_mcp/server.py`        | `PERMIT_DB_PATH` env var, default `data/permits.db`; per-instance `data/building_permits.db` / `data/business_licenses.db` (`applicants`, `permit_applications`) | `db_create_record`, `db_read_record`, `db_update_record`, `db_delete_record` |
| `tax-db-mcp`                 | `mcp_servers/tax_db_mcp/server.py`           | `data/tax_revenue.db` (`properties`, `tax_payments`) | `db_create_record`, `db_read_record`, `db_update_record`, `db_delete_record` |
| `payment-mcp`                | `mcp_servers/payment_mcp/server.py`          | Same `data/tax_revenue.db` as `tax-db-mcp`         | `create_payment_link(assessment_no, quarter, amount_lkr)`, `verify_and_settle_payment(transaction_id)` — simulated gateway, no real payment processor is contacted |
| `records-db-mcp`             | `mcp_servers/records_db_mcp/server.py`       | `data/records_compliance.db` (`public_records`, `foia_requests`) | `db_read_record`, `db_create_record`, `db_update_record`, `redact_pii_text(text)` |

Table/column names passed to every `db_*` tool are validated against a fixed schema whitelist
before being interpolated into SQL; only values are ever bound as parameters.

Knowledge base content lives as Markdown under `knowledge_base/<category>/` and is ingested into
Pinecone via `scripts/ingest_kb_pinecone.py` (chunked with `RecursiveCharacterTextSplitter`,
embedded with `text-embedding-3-small`, partitioned by namespace).

## Key Governance & Security Features

- **On-Behalf-Of (OBO) data scoping** — `case_management_agent` reads the caseworker's identity
  from the `X-User-ID` header, threads it into LangGraph state as `user_id` via `InjectedState`,
  and wraps the raw `case-db-mcp` CRUD tools in ownership-checked tools (`get_my_cases`,
  `get_case_notes`, `add_case_note`, `update_case_status`) in `graph.py` — a caseworker can only
  ever read or modify cases assigned to them.
- **LLM tiering** — each agent declares `spec.targetLlmTier` (`cloud-standard` or `on-prem`) plus
  a concrete `LLM_PROVIDER_KEY` / `LLM_MODEL_NAME` (and optional `LLM_BASE_URL` for an
  OpenAI-compatible vLLM endpoint). This is the mechanism intended to keep PII-bearing workloads
  off shared cloud models; currently only `case_management_agent` is configured on-prem by
  default (`onprem-vllm` / `llama-3-70b-instruct`).
- **Structural PII redaction & exemption checks** — `records_foia_agent`'s `graph.py` enforces an
  exemption-check-before-redaction pipeline: a record's `raw_content` and `is_exempt` fields are
  never bound directly to the LLM. Disclosable records are passed through `redact_pii_text`
  (regex-based scrubbing of SSNs, phone numbers, and email addresses) before the response is
  generated.
- **Agent-to-Agent (A2A) forwarding** — every citizen-facing department agent exposes a
  `consult_citizen_inquiry_agent` tool that forwards questions outside its own domain to the
  Citizen Inquiry Agent's `/chat` endpoint over HTTP (`INQUIRY_AGENT_URL`, default
  `http://localhost:8001/chat`).
- **Multi-instance isolation** — the Permits & Licensing codebase runs as two concurrent,
  independently configured instances (Building Permits / Business Licenses), each with its own
  port and its own SQLite file, with no shared state or locking between them
  (`PERMIT_DB_PATH`, `AGENT_ENV_FILE`).

## Frontend Architecture (`frontend/`)

- **Stack**: React 19 + Vite 8, Tailwind CSS 3, `lucide-react` icons, `react-router-dom` 7,
  `react-markdown` for rendering agent responses.
- **`src/i18n/`** — `LanguageContext.jsx` provides a `t()` lookup over `translations.js`
  (English / Sinhala / Tamil), covering navigation, hero copy, service directory, gazette
  notices, and every chat/agent-facing string.
- **`src/mock/`** — `agentMocks.js` is a fully localized, self-contained mock agent engine (no
  backend required) simulating tool-execution steps and structured response cards per agent kind;
  `officerPersonas.js` assigns a deterministic human-officer persona (name + designation) to each
  new chat session.
- **`src/components/`** — `HeroCarousel` (autoplaying department slideshow with quick-action
  cards), `TickerBanner` (scrolling gazette/circular headlines), `ServiceGrid`,
  `GazetteNoticeCard`, and the chat widget (`ChatWidget` / `ChatMessage` / `DepartmentBadge` /
  `OfficerBadge`).
- **`src/pages/`** — one route per department (`/contact-center`, `/social-services`, `/permits`,
  `/tax-revenue`, `/records`), each embedding the relevant `ChatWidget` with its department seal
  and agent key from `src/mock/departmentData.js`.
- **Mock vs. live backend switch** — `VITE_USE_MOCK_AGENTS` (`frontend/.env`, default `true`)
  toggles `src/services/agentApi.js` between the mock engine and real `POST /chat` requests to
  `http://localhost:<port>/chat` for each agent in `departmentData.js` (ports 8000–8006). The
  Central Portal Agent (`:8007`) is not currently wired into the frontend's agent registry.

## Local Setup & Execution

### Prerequisites

- Python 3.11+ (repo's checked-in `.venv` targets 3.11)
- Node.js 18+ (developed against Node 20)
- A Pinecone index and an OpenAI API key (only required for real backend mode / KB ingestion —
  the frontend runs standalone against its mock engine without either)

### Environment setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in PINECONE_API_KEY, PINECONE_INDEX_NAME, OPENAI_API_KEY

# per-agent department config — copy and adjust as needed
for d in agents/*/; do cp "$d/.env.example" "$d/.env" 2>/dev/null; done
```

### Ingest the knowledge base (one-time, requires Pinecone + OpenAI keys)

```bash
python scripts/ingest_kb_pinecone.py
```

### Start the agent services

Each agent is a standalone FastAPI app; MCP servers are spawned automatically by each agent's
LangGraph tool-binding step, so nothing needs to be started separately for them. Run each agent
in its own terminal (or background it):

```bash
# Cloud-tier agents
uvicorn agents.central_portal_agent.main:app --port 8007
uvicorn agents.citizen_inquiry_agent.main:app --port 8001
uvicorn agents.benefits_eligibility_agent.main:app --port 8000
uvicorn agents.tax_assistance_agent.main:app --port 8004
uvicorn agents.records_foia_agent.main:app --port 8006

# On-prem-tier agent
uvicorn agents.case_management_agent.main:app --port 8005

# Permits & Licensing — two isolated instances of the same codebase
AGENT_ENV_FILE=.env.building_permits uvicorn agents.permit_licensing_agent.main:app --port 8002
AGENT_ENV_FILE=.env.business_licenses uvicorn agents.permit_licensing_agent.main:app --port 8003
```

Each service exposes `GET /health` and `POST /chat` (`{"message", "session_id", "context"}` →
`{"response"}`), matching the WSO2 Agent Manager deployment runtime contract.

### Launch the frontend

```bash
cd frontend
npm install
npm run dev
```

By default (`VITE_USE_MOCK_AGENTS=true`) the frontend needs no backend at all. Set
`VITE_USE_MOCK_AGENTS=false` in `frontend/.env` to point it at the running agent services above.

### Verification

```bash
# Confirms Building Permits (:8002) and Business Licenses (:8003) run concurrently
# with fully isolated SQLite state
python scripts/test_multi_instance_permits.py

# Frontend production build check
cd frontend && npm run build
```

## Repository Layout (current)

```
agora/
├── agents/                  # one directory per agent codebase (manifest.yaml, prompt.md, graph.py, tools.py, main.py)
├── mcp_servers/              # stdio MCP tool servers (one directory per server)
├── data/                     # per-department SQLite databases
├── knowledge_base/           # Markdown KB source docs, ingested into Pinecone by department namespace
├── scripts/                  # ingestion and verification scripts
├── frontend/                 # React + Vite citizen portal UI
├── docs/demo-blueprint.html  # visual walkthrough of the demo scenario
├── PLAN.md                   # original demo blueprint / design intent
├── requirements.txt          # Python dependencies (shared across all agents + MCP servers)
└── README.md                 # this file
```
