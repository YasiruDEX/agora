# Case Management DB Agent

**Ballerina, no MCP** — the direct-database twin of [`case-management-agent`](../case-management-agent).
Same `/chat` contract, same Agent Manager wiring, same two governance boundaries. The
difference is where the case store lives: this agent owns an embedded encrypted SQLite
database and implements its tools as in-process Ballerina functions, instead of calling a
remote MCP server.

## Why both variants exist

The MCP twin gets tool-scope enforcement *from the platform* — the MCP server refuses the
tools the agent's identity isn't scoped into. Take MCP away and that enforcement has to come
from somewhere. This agent is the answer to "somewhere": both boundaries move inside the
process, stay real, and stay visible in the logs.

|                  | [`case-management-agent`](../case-management-agent) | this agent |
|---|---|---|
| Case store       | remote Python MCP server | embedded SQLite, in-process |
| Tool transport   | MCP (streamable HTTP) | Ballerina function calls ([`tools.bal`](tools.bal)) |
| Scope gate       | enforced by the MCP server | enforced by `authorizeTool()` |
| OBO identity     | introspected by the MCP server | introspected by `introspect()` |
| Outbound auth    | OAuth2 AgentID client credentials | none — nothing is called out to |
| Encryption at rest | MCP server's concern | this agent's ([`fernet.bal`](fernet.bal)) |
| Boundary tests   | need a second process running | `./test.sh` |

Point both at the same database file and they are interchangeable — see
[Database compatibility](#database-compatibility).

## Two boundaries, both real, both testable

1. **Tool scope.** The agent implements all 7 case-system operations; its identity is granted
   3 (`case_search`, `case_read`, `case_notes_write`). [`TOOL_SPECS`](tools.bal) is the single
   source of truth, and two independent layers derive from it:
   - the LLM's tool list is the granted subset, so the model cannot *ask* for the other 4;
   - `authorizeTool()` refuses the other 4 before any SQL runs, so a call arriving by any
     other path is still denied — and the denial is logged at `WARN`.

   The 4 ungranted tools are fully implemented and working. That's deliberate: a scope gate
   guarding functions that don't exist proves nothing. What stops `case_close` is the grant.

2. **On-behalf-of identity.** Every tool call must carry an `X-OBO-Token` that introspects to
   a caseworker (RFC 7662-style stand-in). Results are restricted to that caseworker's own
   assigned cases, and ownership is re-checked **per `case_id`** — so a caseworker who learns
   another caseworker's case id is *denied*, not merely missing it from search results. Run
   one instance with two different tokens and `case_search` returns two different case lists.

Note authorship comes from the introspected token, never from the model's arguments — the
author of a case note is an identity fact, not an LLM output.

## How it's wired

```
Caseworker → POST /chat (X-OBO-Token) → LLM tool loop (3 tools only)
                                                │
                                                ▼
                                    authorizeTool()  ── scope + identity, denials logged
                                                │
                                                ▼
                                    tools.bal → store.bal → SQLite (Fernet-encrypted fields)
```

- [`main.bal`](main.bal) — HTTP service, OpenAI function-calling loop, retry/degradation.
- [`tools.bal`](tools.bal) — the tool table, the policy gate, and the 7 tool implementations.
- [`store.bal`](store.bal) — SQL over embedded SQLite via `ballerinax/java.jdbc`.
- [`fernet.bal`](fernet.bal) — Fernet encrypt/decrypt, wire-compatible with Python's `cryptography`.
- [`seed.bal`](seed.bal) — idempotent startup seeding from [`seed/`](seed).
- [`observability.bal`](observability.bal) — the logging contract (see [Logging](#logging)).
- `import ballerinax/amp as _;` wires in Agent Manager's tracing extension.

`POST /debug/toolCall` is a **test-only** escape hatch carried over from the MCP twin's
`/debug/mcpCall`: it calls any named tool directly, bypassing the LLM, so a test can prove the
*gate* refuses the ungranted tools rather than merely that the prompt never offers them. It is
deliberately not retry/degrade-wrapped, so a test sees the raw refusal.

## Setup

Requires Ballerina 2201.13.x+ and a JDK (Ballerina's `amp` extension depends on `openjdk`):

```bash
brew install ballerina   # pulls in openjdk automatically
bal version
```

```bash
cd agents/case-management-db-agent
cp .env.example .env
# fill in OPENAI_API_KEY and CASEMGMT_ENCRYPTION_KEY
```

`CASEMGMT_ENCRYPTION_KEY` is required and has no fallback — the agent refuses to start without
it. Generate one for a fresh database:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Nothing else needs to be running. On first start the agent creates its schema and seeds itself
from `seed/*.json`.

## Run

```bash
./run.sh                        # builds if needed, loads .env, runs on port 8000
LOG_LEVEL=DEBUG ./run.sh        # full SQL + LLM-turn trace
ENV_FILE=.env.staging ./run.sh  # load a different env file
```

Or manually: `bal build && JAVA_HOME=$(brew --prefix openjdk) java -jar target/bin/case_management_db_agent.jar`
(Ballerina has no bundled JDK on this platform — `bal build`/`bal run` resolve it
automatically, but running the built jar directly needs `JAVA_HOME` pointed at Homebrew's
`openjdk`, not the JRE stub at `/usr/bin/java`.)

**Port is a Ballerina `configurable`, not a plain env var.** AM's build step needs a
statically-resolvable port to generate the OpenAPI/server info for a Ballerina agent — a port
computed from `os:getEnv(...)` at runtime fails that step
(`Unsupported expression found for the server port value`). So `port` in `main.bal` is
`configurable int port = 8000;`, and the only supported override is `BAL_CONFIG_VAR_PORT=<port>`
(**not** `PORT`). AM always deploys on the default 8000; the override is for running several
local instances side by side.

| Env var | Purpose |
|---|---|
| `COUNTY_NAME` | Branding in the system prompt |
| `CASEMGMT_ENCRYPTION_KEY` | **Required.** Fernet key for citizen PII + case-note content |
| `CASEMGMT_DB_PATH` | SQLite file (default `data/case_mgmt.db`) |
| `CASEMGMT_SEED_DIR`, `CASEMGMT_SEED_ON_START` | Startup seeding |
| `CASEMGMT_OBO_TOKENS_JSON` | Override the caseworker token map (same shape as the MCP twin's) |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Direct OpenAI (dev/local) |
| `LOG_LEVEL` | `ERROR`/`WARN`/`INFO`/`DEBUG` (default `INFO`) |
| `BAL_CONFIG_VAR_PORT` | Local port override (see note above — not `PORT`) |

There is **no** `MCP_SERVER_URL` and no `AMP_AGENTID_*` here, unlike the MCP twin: this agent
makes no outbound MCP call, so it has no MCP proxy to authenticate to.

## Logging

[`observability.bal`](observability.bal) holds the contract; the rest of the package is written
against it. Two rules make the output greppable without a bespoke parser:

1. The log message is a dotted **event name**, never a sentence — `tool.scope.denied`,
   `db.notes.decrypt.failed`, `chat.llm.turn`. Human explanation goes in a `detail` field.
2. Every line served under a request carries `requestId` (and `caseworker` once known), so one
   conversation reconstructs with `grep 'requestId="8625a96f"'`.

| Level | What goes here |
|---|---|
| `DEBUG` | Mechanics for active diagnosis: each SQL access with row counts, each LLM turn, redacted tool arguments, per-step latency |
| `INFO` | Normal request lifecycle and startup: request received/completed, tool invoked/completed, schema init, seed summary, listener up |
| `WARN` | Refused or degraded but still serving: missing/unknown OBO token, out-of-scope tool attempt, ownership denial, a retried attempt, step budget exhausted |
| `ERROR` | Could not serve the request: DB failure, LLM failure, decrypt failure, exhausted retries |

**A policy denial is a `WARN`, not an `ERROR`** — it means the security boundary did its job.
`ERROR` is reserved for "this agent is not working", so alerting on `ERROR` stays meaningful.

Three things never reach a log line: secrets (fingerprinted to `<set:44 chars>`), note bodies
and other free text (truncated by `redact()` with a `…(+23 chars)` marker), and raw error
objects at default level. That last one matters more than it sounds — passing an error straight
to `log:print*` serialises its whole detail record, which for an HTTP client error means every
response header including `Set-Cookie`, thousands of characters, repeated on every retry.
`errSummary()` reduces it to `cause="Unauthorized (status 401)"`; the raw object is logged once
at `DEBUG`.

`LOG_LEVEL=DEBUG ./run.sh` sets the level; `format = "json"` in `Config.toml` (see
[`Config.toml.example`](Config.toml.example)) switches the whole package to structured JSON with
no code change, since `ballerina/log` does the formatting.

One request, end to end, at `DEBUG`:

```
[INFO ] chat.request.received requestId="8625a96f" session="s-joan-4" messageChars=102 oboPresented=true
[DEBUG] chat.request.body     requestId="8625a96f" prompt="Add a note to CASE-1003 saying the recertification…"
[DEBUG] chat.llm.turn         requestId="8625a96f" turn=1 model="gpt-4o-mini" toolCalls=1 durationMs=1063.5
[INFO ] tool.invoke.start     requestId="8625a96f" tool="case_notes_write" args="case_id=CASE-1003 note=The recert…(+23 chars)"
[DEBUG] auth.obo.ok           requestId="8625a96f" tool="case_notes_write" caseworker="joan.ellis"
[DEBUG] db.cases.read.hit     requestId="8625a96f" caseId="CASE-1003" status="open" durationMs=0.9
[INFO ] db.notes.written      requestId="8625a96f" caseId="CASE-1003" author="Joan Ellis" noteId=8 contentChars=71 durationMs=3.4
[INFO ] tool.invoke.done      requestId="8625a96f" tool="case_notes_write" caseworker="joan.ellis" refused=false durationMs=6.1
[DEBUG] chat.llm.turn         requestId="8625a96f" turn=2 model="gpt-4o-mini" toolCalls=0 durationMs=1016.5
[INFO ] chat.request.completed requestId="8625a96f" caseworker="joan.ellis" attempts=1 responseChars=167 durationMs=2088.7
```

## Resilience

A genuine infrastructure failure (SQL error, decrypt failure, LLM unreachable) is retried with
backoff, then degraded to a plain-language "I can't get to the case system right now" — the
caseworker never sees a stack trace. A **policy denial is never retried**: it comes back as a
normal tool result with `isError`, is fed to the model verbatim, and the model relays the
specific reason ("that case isn't assigned to you") instead of a generic apology.

Retries are suppressed once an attempt has written to the store. The MCP twin retries the whole
chat loop blindly; here the writes are ours, so a replay could append a caseworker's note twice.
`MUTATING_TOOLS` drives that, and a test asserts every write path is listed in it.

## Concurrency

The resource methods are `isolated`, which is what lets Ballerina serve them in parallel —
without it the runtime serialises every request and one caseworker's two-second LLM turn blocks
everyone else. Verified: four concurrent `/chat` requests complete in 3.2s wall clock rather
than ~8s, with all four `chat.request.received` lines at the same millisecond.

The store deliberately runs a **single** JDBC connection: SQLite serialises writers, so writes
queue rather than racing into `SQLITE_BUSY`. The queue isn't the bottleneck — the LLM call is.

## Database compatibility

The schema and the field-level Fernet encryption match
[`case-management-mcp-server/store.py`](../../mcp-servers/case-management-mcp-server/store.py)
exactly, so both agents can be pointed at one database file:

```bash
CASEMGMT_DB_PATH=../../mcp-servers/case-management-mcp-server/data/case_mgmt.db ./run.sh
```

Two details make that true rather than approximately true, both in [`store.bal`](store.bal):
encrypted columns are read back with `CAST(col AS TEXT)` (a Fernet token is ASCII in a `BLOB`
column), and written as `byte[]` rather than `string` — SQLite is dynamically typed, so binding
a string would store `TEXT`, and Python's store does `Fernet.decrypt(bytes(v))`, which raises
`TypeError` on a `str`.

Verified in both directions: Python's `cryptography.fernet` decrypts every row this agent
writes (notes and citizen PII), and this agent reads notes written by the Python store.

## Testing

```bash
./test.sh                    # whole suite
./test.sh --groups fernet    # fernet | interop | policy | scope | identity | store | encryption | concurrency | observability
```

**65 tests, all passing.** `test.sh` runs against a throwaway SQLite database and an empty
`OPENAI_API_KEY`, so the suite never touches a developer's real key or the database the agent
serves from.

The suite covers, in rough order of what would hurt most if it broke:

- **Cross-implementation Fernet** ([`fernet_test.bal`](tests/fernet_test.bal)) — four tokens
  generated by Python's `cryptography.fernet` under a fixed test key, including multibyte text,
  a multi-block payload, and empty plaintext. A self-consistent round trip proves nothing about
  wire compatibility, which is the entire reason `fernet.bal` exists. Plus: tampered ciphertext
  rejected on the HMAC, wrong version byte rejected, malformed tokens rejected rather than
  panicking, non-deterministic IVs, and the timestamp field checked against the byte layout
  Python actually wrote.
- **Policy** ([`policy_test.bal`](tests/policy_test.bal)) — the model is offered exactly the
  granted tools; `TOOL_SPECS` and `ALL_TOOLS` cannot drift; every declared tool has a real
  implementation behind the gate; all 4 ungranted tools refused even with a valid token; scope
  checked before identity; inactive tokens never resolve to a fallback caseworker.
- **Store** ([`store_test.bal`](tests/store_test.bal)) — against a real database: disjoint
  per-caseworker result sets, keyword and case-insensitive search, ownership denial per
  `case_id`, refused writes leaving the store untouched, note encryption round trip, tool
  payload shapes matching the MCP twin's, note author taken from the token not the arguments.
- **Concurrency** ([`concurrency_test.bal`](tests/concurrency_test.bal)) — 12 interleaved
  searches never leak a case across caseworkers, 10 concurrent writes each land exactly once,
  24 concurrent encryptions produce distinct IVs, and per-request identity doesn't bleed.
- **Observability** ([`observability_test.bal`](tests/observability_test.bal)) — redaction
  truncates and says how much it dropped, fingerprints never reveal a prefix of the secret,
  request ids are unique, and `errSummary()` keeps the status while dropping response headers
  (with an explicit assertion that a `Set-Cookie` value cannot reach a log line).

### Verified live, end to end

Against a running instance with real OpenAI calls:

```bash
# Same instance, two caseworkers, two case lists — PLAN.md §13.5's visual
curl -s -X POST http://127.0.0.1:8000/chat -H 'Content-Type: application/json' \
  -H 'X-OBO-Token: obo_joan_ellis_4a7c9f' \
  -d '{"message": "List my current cases and summarize each one briefly."}'

curl -s -X POST http://127.0.0.1:8000/chat -H 'Content-Type: application/json' \
  -H 'X-OBO-Token: obo_renee_alvarez_1e6b2d' \
  -d '{"message": "List my current cases and summarize each one briefly."}'

# Scope violation, attempted and denied by the agent's own gate — PLAN.md §13.4's centerpiece
curl -s -X POST http://127.0.0.1:8000/debug/toolCall -H 'Content-Type: application/json' \
  -H 'X-OBO-Token: obo_joan_ellis_4a7c9f' \
  -d '{"tool": "citizen_profile_read", "arguments": {"citizen_id": "CIT-3001"}}'
```

Confirmed:

- Joan and Renee get disjoint, correct case lists from the same running instance.
- Asked to close a case or read a citizen's SSN, the model declines directly — it was never
  given those tools, so it doesn't attempt the call.
- `/debug/toolCall` proves `citizen_profile_read`, `case_close` and `case_status_update` are
  refused by the scope gate, and that Joan is denied reading Renee's `CASE-1005` (`case_read`,
  an in-scope tool, wrong owner) — two independent boundaries, both enforced, both logged at
  `WARN` naming the attempted tool and the grant it was measured against.
- A request with no `X-OBO-Token` is denied with a clear message; the LLM relays it rather than
  returning empty or crashing.
- The agent writes a note on request, and it round-trips out of the encrypted store.
- Graceful degradation: with an unreachable LLM, 2 `WARN` retries with backoff then one `ERROR`,
  and a normal `200` carrying the plain-language message. The whole trail is 3 log lines and
  548 characters — the pre-`errSummary()` version was ~4 KB and included Cloudflare's
  `Set-Cookie`.

`GET /health` is a readiness probe, not just liveness: it queries the store and returns `503` if
the database is unreadable.

```json
{"status":"ok","county":"Riverside County","store":"data/case_mgmt.db","cases":6,
 "grantedTools":["case_search","case_read","case_notes_write"]}
```

## Credentials for testing (fictional, local dev only)

Pass as the `X-OBO-Token` header on `/chat` or `/debug/toolCall`:
`obo_joan_ellis_4a7c9f` (Joan Ellis, CASE-1001–1003) and `obo_renee_alvarez_1e6b2d`
(Renee Alvarez, CASE-1004–1006).

## Known workaround

Reading `tool_calls` directly off a `chat:ChatCompletionResponseMessage` — by `?.` or by member
access — makes `ballerina/sql`'s compiler extension abort the build with
`The compiler extension in package 'ballerina:sql:1.19.0' failed to complete. Symbol is 'null'`.
The MCP twin never hits it because that package has no SQL in it. `main.bal` projects the
response through a small open record (`AssistantTurn`) via `cloneWithType()`, which keeps the
tool calls fully typed and gives the plugin nothing to choke on. If the plugin bug is fixed
upstream, that type and its `cloneWithType()` call can go.
