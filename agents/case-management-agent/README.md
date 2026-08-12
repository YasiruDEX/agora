# Case Management Agent

**Ballerina**, native MCP client — deliberately a different runtime than the two LangChain
agents in this repo, per [`PLAN.md`](../../PLAN.md) §5: proves Agent Manager's governance
(MCP tool scoping, on-behalf-of identity) applies identically no matter what the agent is
written in.

Talks to the dedicated [Case Management MCP Server](../../mcp-servers/case-management-mcp-server)
— the MCP-scoping centerpiece of this demo (PLAN.md §7-8). Single instance, Social Services
only (not fanned out, on purpose).

## Two boundaries, both real, both testable without Agent Manager

1. **MCP tool scope.** The server exposes 7 tools; this agent's LLM tool loop only ever
   defines 3 of them (`case_search`, `case_read`, `case_notes_write`) — the model literally
   cannot ask for the other 4. As defense in depth, the MCP server *also* rejects those 4 for
   this agent's API key even if something bypassed the LLM (see `/debug/mcpCall` below).
2. **On-behalf-of identity.** Every MCP call carries an `X-OBO-Token` identifying which
   caseworker the agent is acting for. Run the *same* running instance with two different
   tokens and `case_search` returns two different case lists — same code, same API key,
   different identity.

## How it's wired

```
Caseworker → POST /chat (X-OBO-Token header) → LLM tool loop (3 tools only)
                                                        │
                                                        ▼ (X-MCP-API-Key + X-OBO-Token)
                                      Case Management MCP Server (scope + identity enforced)
```

- `main.bal` builds a manual OpenAI function-calling loop (`ballerinax/openai.chat`) bound to
  exactly `SCOPED_TOOLS` — no dynamic tool discovery from the MCP server, so there's no path
  by which the model could be offered a 4th tool.
- Every MCP call goes through `callMcpTool`, using `ballerina/mcp`'s native
  `StreamableHttpClient`, sending both the agent's fixed `MCP_API_KEY` and the per-request
  on-behalf-of token.
- `POST /debug/mcpCall` is a **test-only** escape hatch that calls any named MCP tool directly
  with the same credentials the agent itself uses — it exists purely so a test script can
  prove the out-of-scope tools are denied by the *server*, not just "never offered" by this
  agent's own prompt. The `/chat` path never touches this route.
- `import ballerinax/amp as _;` wires in Agent Manager's tracing extension, per its Build
  Details panel for Ballerina-based agents (Ballerina 2201.13.x+).

## Setup

Requires Ballerina 2201.13.x+ and a JDK (Ballerina's `amp` extension depends on `openjdk`):

```bash
brew install ballerina   # pulls in openjdk automatically
bal version
```

```bash
cd agents/case-management-agent
cp .env.example .env
# fill in OPENAI_API_KEY; MCP_SERVER_URL/MCP_API_KEY already match the local MCP server defaults
```

Start the [Case Management MCP Server](../../mcp-servers/case-management-mcp-server) first
(default `http://127.0.0.1:8103/mcp`).

## Run

```bash
./run.sh                       # builds if needed, loads .env, runs on port 8000
ENV_FILE=.env.staging ./run.sh # load a different env file
```

Or manually: `bal build && JAVA_HOME=$(brew --prefix openjdk) java -jar target/bin/case_management_agent.jar`
(Ballerina has no bundled JDK on this platform — `bal build`/`bal run` resolve it
automatically, but running the built jar directly needs `JAVA_HOME` pointed at Homebrew's
`openjdk`, not the JRE stub at `/usr/bin/java`.)

**Port is a Ballerina `configurable`, not a plain env var.** AM's build step needs a
statically-resolvable port to generate the OpenAPI/server info for a Ballerina agent — a
port computed from `os:getEnv(...)` at runtime fails that build step
(`Unsupported expression found for the server port value`). So `port` in `main.bal` is
`configurable int port = 8000;`, and the only supported override is
`BAL_CONFIG_VAR_PORT=<port>` (not `PORT`) — see `.env.example`. AM always deploys on the
default 8000; the override is only for running multiple local instances side by side.

| Env var | Purpose |
|---|---|
| `COUNTY_NAME` | Branding in the system prompt |
| `MCP_SERVER_URL` / `MCP_API_KEY` | Case Management MCP server connection (this agent's fixed identity) |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Direct OpenAI (dev/local) |
| `PORT` | Local port |

## Credentials for testing (fictional, local dev only)

Pass as the `X-OBO-Token` header on `/chat` or `/debug/mcpCall` — see the MCP server's README
for the full table. In short: `obo_joan_ellis_4a7c9f` (Joan Ellis, cases 1001-1003) and
`obo_renee_alvarez_1e6b2d` (Renee Alvarez, cases 1004-1006).

## Testing

Verified end-to-end locally against the running MCP server (real OpenAI calls):

```bash
# Same instance, two caseworkers, two case lists — PLAN.md §13.5's visual
curl -s -X POST http://127.0.0.1:8000/chat -H 'Content-Type: application/json' \
  -H 'X-OBO-Token: obo_joan_ellis_4a7c9f' \
  -d '{"message": "List my current cases and summarize each one briefly."}'

curl -s -X POST http://127.0.0.1:8000/chat -H 'Content-Type: application/json' \
  -H 'X-OBO-Token: obo_renee_alvarez_1e6b2d' \
  -d '{"message": "List my current cases and summarize each one briefly."}'

# MCP scope violation, attempted and denied — PLAN.md §13.4's centerpiece
curl -s -X POST http://127.0.0.1:8000/debug/mcpCall -H 'Content-Type: application/json' \
  -H 'X-OBO-Token: obo_joan_ellis_4a7c9f' \
  -d '{"tool": "citizen_profile_read", "arguments": {"citizen_id": "CIT-3001"}}'
```

Confirmed:
- Joan and Renee get disjoint, correct case lists from the same running instance.
- The LLM, asked to close a case or read a citizen's SSN, declines directly — it was never
  given those tools, so it doesn't even attempt the call.
- `/debug/mcpCall` proves `citizen_profile_read` and `case_close` are denied by the MCP server
  itself with a message naming the scope violation, and that Joan is denied reading Renee's
  case (`case_read`, an in-scope tool, but wrong owner) — two independent boundaries, both
  enforced, both logged server-side.
- A request with no `X-OBO-Token` is denied with a clear message rather than silently
  returning empty or crashing.
