# Citizen Inquiry Agent

Python/LangChain agent that answers Riverside County resident questions from a
department-scoped knowledge base, per [`PLAN.md`](../../PLAN.md) §5/§6.

**One image, one prompt, 5 running instances** — Social Services, Permits & Licensing, Tax &
Revenue, Records & Compliance, Contact Center. Every instance calls the same
[Unified KB MCP Server](../../mcp-servers/unified-kb-mcp-server) at the same
`MCP_SERVER_URL`; the only thing that differs between instances is the injected
`MCP_API_KEY`, and that key is what the MCP server resolves to one department's namespace.
This agent never decides which namespace it can see — it just gets back whatever the four
`kb_*` tools return for its key.

Published to the catalog as [`catalog/citizen-inquiry-agent.yaml`](../../catalog/citizen-inquiry-agent.yaml)
— the demo's stand-in for `amp:agent-kind:create` (there's no live Agent Manager control
plane here, so this manifest is the record of what got "published").

## How it's wired

```
Resident → POST /chat → LangGraph ReAct agent → kb_search / kb_read / kb_write / kb_list_sources
                                                        │
                                                        ▼ (X-MCP-API-Key header)
                                          Unified KB MCP Server (namespace resolved from key)
```

- **Tool binding**: `mcp_tools.py` uses `langchain-mcp-adapters`'
  `MultiServerMCPClient(streamable_http)` to fetch the 4 KB tools at startup, sending
  `X-MCP-API-Key: <MCP_API_KEY>` on every call — including calls the agent makes mid-conversation,
  not just the initial handshake.
- **Grounding**: the system prompt in `agent.py` requires the model to search the KB before
  answering, cite the source article, and say "I don't have that information" rather than
  invent policy/fee/deadline details — the KB is the only source of truth.
- **Scope containment**: if a resident (or a malicious prompt) asks about another
  department's services or tries to `kb_read` another namespace's `doc_id` directly, the MCP
  server denies it — not this agent's judgment. See the MCP server's own isolation tests for
  the enforcement layer; this agent's system prompt is a second, softer line of defense (say
  "that's not my department" instead of guessing), not the actual boundary.

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
| `MCP_SERVER_URL` | Unified KB MCP server endpoint (same for every instance) |
| `MCP_API_KEY` | The credential that actually determines this instance's namespace |
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

Verified end-to-end with two instances running side by side:
- Social Services (8001) correctly answers CalFresh questions with a citation to the source
  article, and cannot be prompt-injected into reading a Tax & Revenue `doc_id` (`tr-001`) —
  the MCP server returns "no article found," not the other department's content.
- Tax & Revenue (8003) correctly declines the same CalFresh question ("I don't have
  information regarding CalFresh...") while answering its own property-tax questions fully —
  same agent code, same tool names, different data reachable, purely from the API key.

This is the demo beat from PLAN.md §13.3: same tool, five departments, five API keys — the
KB server never changes, only the identity does.
