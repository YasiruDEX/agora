# Unified KB MCP Server

Namespace-partitioned knowledge-base MCP server for the Citizen Inquiry Agent, per
[`PLAN.md`](../../PLAN.md) §6. One server, four tools, five department namespaces for
**Riverside County — Department of Citizen Services**:

`social-services` · `permits-licensing` · `tax-revenue` · `records-compliance` · `contact-center`

Every Citizen Inquiry Agent instance talks to the **same** `MCP_SERVER_URL` but presents a
**different** `MCP_API_KEY`. This server resolves that key to exactly one namespace, and every
tool call — search, read, write, list — is scoped to it. Same server, same four tools, five
department instances; only the caller's identity changes.

## Tools

| Tool | Effect |
|---|---|
| `kb_search(query)` | Keyword-ranked search over the caller's namespace |
| `kb_read(doc_id)` | Fetch a specific article from the caller's namespace |
| `kb_write(doc_id, content, source?)` | Create or update an article in the caller's namespace |
| `kb_list_sources()` | List the source article titles the caller's namespace was built from |

Search uses simple keyword-overlap ranking rather than real embeddings — a deliberate
simplification of PLAN.md's open question on vector-store choice. It's enough to demonstrate
namespace isolation and tool behavior, which is the point of this server; swapping in a real
embedding index later wouldn't change the tool contract above.

## Storage & encryption

Embedded local SQLite (`data/kb_store.db`) — no external database. Article **content** is
encrypted at rest with [Fernet](https://cryptography.io/en/latest/fernet/) (AES-128-CBC +
HMAC); article **titles** (the `source` field, used by `kb_list_sources`) are stored in
plaintext since they carry no sensitive content and need to be listable without decrypting
every row. The encryption key stands in for the `amp:git-secret` entry the Platform Admin
would own in the real Agent Manager deployment.

## Setup

Uses the shared virtualenv at the repo root (`../../.venv`) so agents built later can share it.

```bash
cd /path/to/agora
source .venv/bin/activate
pip install -r mcp-servers/unified-kb-mcp-server/requirements.txt
```

Generate an encryption key and set required env vars:

```bash
cd mcp-servers/unified-kb-mcp-server
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# paste the output as KB_ENCRYPTION_KEY in .env
```

| Env var | Default | Purpose |
|---|---|---|
| `KB_MCP_HOST` | `0.0.0.0` | Bind host |
| `KB_MCP_PORT` | `8100` | Bind port |
| `KB_DB_PATH` | `data/kb_store.db` | SQLite file path |
| `KB_ENCRYPTION_KEY` | *(required)* | Fernet key for content-at-rest encryption |
| `KB_API_KEYS_JSON` | *(the 5 department keys below)* | Override/extend the API-key → namespace map |

## Run

```bash
source ../../.venv/bin/activate
set -a; source .env; set +a
python server.py
```

Seeds all 5 namespaces on every startup (idempotent upsert) and serves streamable-HTTP MCP at
`http://<host>:<port>/mcp`.

## Department API keys (fictional, for local dev/testing only)

| Department | Namespace | API key |
|---|---|---|
| Social Services | `social-services` | `kb_live_social-services_8f2a1c` |
| Permits & Licensing | `permits-licensing` | `kb_live_permits-licensing_3d7e90` |
| Tax & Revenue | `tax-revenue` | `kb_live_tax-revenue_b14f6a` |
| Records & Compliance | `records-compliance` | `kb_live_records-compliance_e9c024` |
| Contact Center | `contact-center` | `kb_live_contact-center_5a6b3d` |

Pass the key as either header: `X-MCP-API-Key: <key>` or `Authorization: Bearer <key>`. A
missing or unrecognized key is denied — no namespace defaults to "open."

## Testing

With the server running, run the end-to-end test client (a real MCP client over
streamable-HTTP, one connection per department key plus one invalid key):

```bash
python test_client.py http://127.0.0.1:8100/mcp
```

It asserts:
- each department key only ever sees its own namespace via `kb_list_sources`
- `kb_search` never returns another department's docs
- `kb_read` on another department's `doc_id` is denied, not just empty
- `kb_write` + `kb_read` round-trips within a namespace, and the written doc is still
  invisible to other departments
- an invalid or missing API key is denied outright

## Seed data

`seed/<namespace>.json` holds the starter articles per department (Riverside County, CA —
CalFresh/CalWORKs/Medi-Cal for Social Services, building/business permits for Permits &
Licensing, property tax schedules for Tax & Revenue, vital records/CPRA for Records &
Compliance, and department routing/office-hours/211 for Contact Center). `seed_data.py`
loads them into the store on every server startup.
