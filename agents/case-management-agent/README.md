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
                                                        ▼ (Authorization: Bearer + X-OBO-Token)
                                      Case Management MCP Server (scope + identity enforced)
```

- `main.bal` builds a manual OpenAI function-calling loop (`ballerinax/openai.chat`) bound to
  exactly `SCOPED_TOOLS` — no dynamic tool discovery from the MCP server, so there's no path
  by which the model could be offered a 4th tool.
- **Auth**: `requestAccessToken`/`getAccessToken` mint and cache an OAuth2 access token via
  client-credentials grant (RFC 6749) against `AMP_AGENTID_TOKEN_ENDPOINT`, using the
  `AMP_AGENTID_CLIENT_ID`/`CLIENT_SECRET` Agent Manager injects for this instance, with
  `MCP_SERVER_URL` sent as the `resource` indicator (RFC 8707). The token is cached and
  refreshed ahead of its own expiry (Ballerina equivalent of the Python agents'
  `_TokenCache`). This is layered on top of, not instead of, the existing on-behalf-of
  mechanism — every MCP call still carries `X-OBO-Token` for the caseworker identity. Every
  `callMcpTool` invocation re-checks the token cache, so a token minted at process startup
  never goes stale mid-session.
- The access token is sent as **both** `Authorization: Bearer <token>` and `X-MCP-API-Key:
  <token>` — the Case Management MCP Server is deliberately left unmodified (per this repo's
  standing rule) and only understands the latter header, unlike the other three MCP servers
  in this repo, which also accept `Authorization: Bearer` as a fallback for the same static
  key. Sending both keeps this correct against a real OAuth2-validating proxy in production
  and working against this specific backend today. See `mcpHeaders()`.
- **Resilience**: a genuine transport/platform-level failure (token endpoint down, the MCP
  proxy rejecting a request outside this identity's granted scope, a connection error) is
  retried a few times before the caseworker ever sees anything go wrong; if it's still
  failing after retries, they get a plain-language "I don't have access to that right now"
  instead of an error. This is distinct from an in-band MCP scope/ownership denial (e.g.
  asking for `case_close`, or another caseworker's case) — the server returns those as a
  normal tool result, and the LLM relays the specific reason instead of a generic fallback.
- Every MCP call goes through `callMcpTool`, using `ballerina/mcp`'s native
  `StreamableHttpClient`.
- `POST /debug/mcpCall` is a **test-only** escape hatch that calls any named MCP tool directly
  with the same credentials the agent itself uses — it exists purely so a test script can
  prove the out-of-scope tools are denied by the *server*, not just "never offered" by this
  agent's own prompt. The `/chat` path never touches this route, and this route is
  deliberately not retry/degrade-wrapped so a test script sees the raw denial.
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
# fill in OPENAI_API_KEY and the 4 AMP_AGENTID_* vars from your MCP proxy's registered
# service-account; MCP_SERVER_URL already matches the local MCP server default
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
| `MCP_SERVER_URL` | Case Management MCP server connection — also the OAuth2 resource indicator for the AgentID token |
| `AMP_AGENTID_CLIENT_ID`, `AMP_AGENTID_CLIENT_SECRET` | This instance's AgentID service-account credentials |
| `AMP_AGENTID_TOKEN_ENDPOINT` | Where to request access tokens |
| `AMP_AGENTID_SCOPES` | Scopes requested on each token |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Direct OpenAI (dev/local) |
| `BAL_CONFIG_VAR_PORT` | Local port override (see note above — not `PORT`) |

## Credentials for testing (fictional, local dev only)

Pass as the `X-OBO-Token` header on `/chat` or `/debug/mcpCall` — see the MCP server's README
for the full table. In short: `obo_joan_ellis_4a7c9f` (Joan Ellis, cases 1001-1003) and
`obo_renee_alvarez_1e6b2d` (Renee Alvarez, cases 1004-1006).

## Testing

**OAuth2 flow verified end-to-end** against the real (unmodified) MCP server, using a
throwaway local stand-in for the AgentID token endpoint. Confirmed: `bal build` succeeds with
the OAuth2 changes; the agent mints exactly one token across five back-to-back requests (token
caching works — see the fake IDP's request log); Joan and Renee still get correct, disjoint
case lists; a note write succeeds; `case_close` is still denied as an MCP scope violation with
the token-based auth in place; a missing `X-OBO-Token` is still denied. Also caught and fixed
a real bug in the process: the token-fetch HTTP client hit the same HTTP/2 h2c-upgrade failure
against the (Python/uvicorn-based) local test IDP that the MCP client hit earlier against the
Case Management MCP Server — fixed the same way, forcing `httpVersion = http:HTTP_1_1` on the
token client too (see `requestAccessToken`).

Separately, verified graceful degradation by pointing `AMP_AGENTID_TOKEN_ENDPOINT` at an
unreachable host: the agent retried 3 times with backoff, then returned a normal `200` with
the plain-language "I don't have access to that right now" message — never a raw error to the
caseworker.

Previously verified end-to-end locally against the running MCP server (real OpenAI calls,
pre-OAuth2):

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
