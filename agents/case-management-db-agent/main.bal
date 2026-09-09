// Case Management DB Agent — Ballerina, no MCP: the case database is handled inside the agent.
//
// This is the direct-database twin of ../case-management-agent. Same /chat contract, same
// governance story, same Agent Manager wiring — the difference is where the case store lives:
//
//                    ../case-management-agent          this agent
//   case store       remote Python MCP server          embedded SQLite, in-process
//   tool transport   MCP (streamable HTTP)             Ballerina function calls (tools.bal)
//   scope gate       enforced by the MCP server        enforced by authorizeTool()
//   OBO identity     introspected by the MCP server    introspected by introspect()
//   outbound auth    OAuth2 AgentID client credentials none needed — nothing is called out to
//
// Keeping the pair means the same governance question can be asked of two very different
// deployment shapes: with MCP, the platform enforces tool scope for you; without it, the
// agent has to enforce its own, and the enforcement has to be visible in the logs to be
// worth anything. That is why observability.bal exists as its own file with a documented
// level policy rather than scattered log calls.
//
// Agent Manager readiness (unchanged from the MCP twin, so both deploy the same way):
//   - POST /chat on port 8000, {message, session_id, context} -> {response, session_id}
//   - `port` is a `configurable`, statically resolvable for AM's build-time OpenAPI step
//   - `import ballerinax/amp as _;` wires in AM's tracing extension
//   - GET /health is a real readiness probe: it touches the database, not just the process
import ballerina/http;
import ballerina/lang.runtime;
import ballerina/log;
import ballerina/time;

import ballerinax/amp as _;
import ballerinax/openai.chat;

final chat:Client openAiClient = check new ({auth: {token: openAiApiKey}});

// A failed attempt is only safe to retry if it didn't already change the database. With the
// store in-process these writes are ours, so a blind retry could append a caseworker's note
// twice — this flag is what stops that.
final readonly & string[] MUTATING_TOOLS =
    ["case_notes_write", "case_status_update", "citizen_profile_write", "case_close"];

type AttemptState record {|
    boolean mutated = false;
|};

// One assistant turn, projected out of the OpenAI response.
//
// This exists to work around a compiler-plugin bug, not for modelling reasons: reading
// `tool_calls` directly off a `chat:ChatCompletionResponseMessage` — by `?.` or by member
// access — makes ballerina/sql's compiler extension abort the build with
// "The compiler extension in package 'ballerina:sql:1.19.0' failed to complete. Symbol is
// 'null'". The MCP twin never hit it because it has no SQL in the package; this agent does.
// Projecting the response message through cloneWithType() gives the plugin nothing to choke
// on while keeping the tool calls fully typed. Deliberately an *open* record so the extra
// fields OpenAI returns (role, refusal, annotations, …) are carried rather than rejected.
//
// If the plugin bug is fixed upstream, this type and its cloneWithType() call can go and
// `assistantMsg?.tool_calls` can be read directly again.
type AssistantTurn record {
    string? content = ();
    chat:ChatCompletionMessageToolCalls tool_calls = [];
};

isolated function buildSystemPrompt() returns string {
    return string `You are the Case Management Agent for ${countyName}, helping a caseworker summarize cases and draft next steps.

CAPABILITIES:
- case_search: search or list the caseworker's own assigned cases
- case_read: read a case's full details and notes
- case_notes_write: add a note to one of the caseworker's own cases

RULES YOU MUST FOLLOW:
1. SCOPE: You only have these three tools. If asked to do something else (change a case's status, close a case, or read/edit a citizen's profile), explain plainly that this action is outside your granted scope and the caseworker should use the case management system directly for that.
2. OWN CASES ONLY: You act strictly on behalf of the current caseworker. Never claim knowledge of a case that case_search/case_read did not return to you.
3. GROUNDING: Base summaries and next-step suggestions only on what case_read/case_search actually returned — never invent case details.
4. CITE: When summarizing, reference the case_id and note authors/dates so the caseworker can verify.`;
}

// --- HTTP contract --------------------------------------------------------------------------

type ChatRequest record {|
    string message;
    string? session_id = ();
    map<json>? context = ();
|};

type ChatResponse record {|
    string response;
    string? session_id = ();
|};

type HealthResponse record {|
    string status;
    string county;
    string store;
    int cases;
    string[] grantedTools;
|};

type DebugToolRequest record {|
    string tool;
    map<json> arguments = {};
|};

type DebugToolResponse record {|
    boolean isError;
    string text;
|};

// Ballerina answers a POST with 201 Created unless told otherwise, and a chat turn creates no
// resource. The two Python agents in this repo (FastAPI) answer /chat with 200, so these
// wrappers keep all three agents on one contract — the portal client only checks res.ok, but
// an agent fleet that disagrees with itself about status codes is a trap for the next caller.
type ChatOk record {|
    *http:Ok;
    ChatResponse body;
|};

type DebugToolOk record {|
    *http:Ok;
    DebugToolResponse body;
|};

// The caseworker identity travels in a header; the `context.obo_token` fallback exists because
// some Agent Manager front ends forward a JSON context rather than arbitrary headers.
isolated function extractOboToken(http:Request req, ChatRequest body) returns string? {
    string|http:HeaderNotFoundError headerVal = req.getHeader("X-OBO-Token");
    if headerVal is string {
        return headerVal;
    }
    map<json>? context = body.context;
    if context is map<json> {
        json? fromContext = context["obo_token"];
        if fromContext is string {
            return fromContext;
        }
    }
    return ();
}

// --- LLM tool loop ---------------------------------------------------------------------------
//
// Errors that propagate out of here are infrastructure failures (SQL error, decrypt failure,
// LLM unreachable) — the caller retries those. Policy decisions do not propagate: they arrive
// as ToolOutcome{isError: true} and are fed back to the model as tool output, so the model can
// tell the caseworker the actual reason ("that case isn't assigned to you") instead of a
// generic apology.
isolated function runChatLoop(ReqCtx ctx, string userMessage, string? oboToken, AttemptState state)
        returns string|error {
    chat:ChatCompletionRequestMessage[] messages = [
        {role: "system", content: buildSystemPrompt()},
        {role: "user", content: userMessage}
    ];

    foreach int turn in 1 ... MAX_LLM_TURNS {
        decimal turnStarted = time:monotonicNow();
        chat:CreateChatCompletionRequest request = {
            model: openAiModel,
            messages,
            tools: chatTools,
            temperature: 0
        };
        chat:CreateChatCompletionResponse response = check openAiClient->/chat/completions.post(request);
        if response.choices.length() == 0 {
            log:printWarn("chat.llm.empty", requestId = ctx.requestId, turn = turn);
            return "(no response)";
        }

        AssistantTurn assistantMsg = check response.choices[0].message.cloneWithType();
        chat:ChatCompletionMessageToolCalls toolCalls = assistantMsg.tool_calls;
        log:printDebug("chat.llm.turn", requestId = ctx.requestId, turn = turn, model = openAiModel,
                toolCalls = toolCalls.length(), durationMs = elapsedMs(turnStarted));

        if toolCalls.length() == 0 {
            return assistantMsg.content ?: "(no response)";
        }

        messages.push({role: "assistant", content: assistantMsg.content, tool_calls: toolCalls});

        foreach chat:ChatCompletionMessageToolCall|chat:ChatCompletionMessageCustomToolCall call in toolCalls {
            if !(call is chat:ChatCompletionMessageToolCall) {
                log:printWarn("chat.llm.toolcall.unsupported", requestId = ctx.requestId, turn = turn);
                continue;
            }
            string toolName = call.'function.name;
            map<json> args = parseToolArgs(ctx, toolName, call.'function.arguments);

            // Recorded before the call, not after: a write that fails partway through has
            // still potentially touched the database, so the retry must be suppressed either
            // way.
            if MUTATING_TOOLS.indexOf(toolName) != () {
                state.mutated = true;
            }

            ToolOutcome outcome = check invokeTool(ctx, toolName, args, oboToken);
            messages.push({
                role: "tool",
                tool_call_id: call.id,
                content: outcome.isError ? string `ERROR: ${outcome.text}` : outcome.text
            });
        }
    }

    log:printWarn("chat.budget.exhausted", requestId = ctx.requestId, maxTurns = MAX_LLM_TURNS,
            detail = "returned a rephrase prompt instead of looping further");
    return "I wasn't able to finish that within my step budget — please try rephrasing or ask " +
            "about one case at a time.";
}

// A model can emit malformed JSON arguments. That's a bad turn, not a broken agent: log it and
// let the tool refuse on the missing argument, which gives the model a message it can recover
// from on the next turn.
isolated function parseToolArgs(ReqCtx ctx, string toolName, string raw) returns map<json> {
    json|error parsed = raw.fromJsonString();
    if parsed is error {
        log:printWarn("chat.llm.toolargs.malformed", cause = errSummary(parsed),
                requestId = ctx.requestId, tool = toolName, raw = redact(raw));
        return {};
    }
    if parsed is map<json> {
        return parsed;
    }
    log:printWarn("chat.llm.toolargs.unexpected", requestId = ctx.requestId, tool = toolName,
            detail = "tool arguments were valid JSON but not an object");
    return {};
}

service / on new http:Listener(port) {

    isolated function init() returns error? {
        logStartup("agent.starting", string `${countyName} Case Management DB Agent (no MCP)`);
        log:printInfo("agent.config", port = port, store = dbPath, model = openAiModel,
                openAiKey = fingerprint(openAiApiKey), encryptionKey = fingerprint(encryptionKeyB64),
                grantedTools = GRANTED_TOOLS.toString(),
                ungrantedTools = (from string t in ALL_TOOLS
                    where !isGrantedTool(t)
                    select t).toString(),
                caseworkers = oboTokens.length(), seedOnStart = seedOnStart);

        check initSchema();
        if seedOnStart {
            check seedAll();
        } else {
            log:printDebug("seed.skipped", detail = "CASEMGMT_SEED_ON_START is not 'true'");
        }
        log:printInfo("agent.ready", endpoint = string `http://0.0.0.0:${port}/chat`);
    }

    // Readiness, not just liveness: it runs a query, so a process that is up but cannot read
    // its store reports itself as unhealthy instead of accepting traffic it can't serve.
    isolated resource function get health() returns HealthResponse|http:ServiceUnavailable {
        int|error cases = dbClient->queryRow(`SELECT COUNT(*) FROM cases`);
        if cases is error {
            log:printError("health.store.unreachable", cause = errSummary(cases), store = dbPath);
            return <http:ServiceUnavailable>{
                body: {status: "unavailable", detail: "case store is not readable"}
            };
        }
        return {
            status: "ok",
            county: countyName,
            store: dbPath,
            cases: cases,
            grantedTools: GRANTED_TOOLS
        };
    }

    isolated resource function post chat(http:Request req, @http:Payload ChatRequest body) returns ChatOk {
        ReqCtx ctx = newReqCtx("POST /chat", body.session_id);
        decimal started = time:monotonicNow();
        string? oboToken = extractOboToken(req, body);

        log:printInfo("chat.request.received", requestId = ctx.requestId, session = ctxSession(ctx),
                messageChars = body.message.length(), oboPresented = oboToken is string);
        log:printDebug("chat.request.body", requestId = ctx.requestId, prompt = redact(body.message, 120));

        if oboToken is () {
            // WARN and continue rather than 400: the tools refuse individually and the model
            // relays a specific reason, which is more useful to a caseworker than a bare
            // status code — and it keeps the "identity is enforced at the tool, not the edge"
            // property visible.
            log:printWarn("auth.obo.absent", requestId = ctx.requestId,
                    detail = "no X-OBO-Token header and no context.obo_token — every tool call will be denied");
        }

        error? lastErr = ();
        foreach int attempt in 1 ... MAX_ATTEMPTS {
            AttemptState state = {};
            string|error result = runChatLoop(ctx, body.message, oboToken, state);
            if result is string {
                log:printInfo("chat.request.completed", requestId = ctx.requestId,
                        session = ctxSession(ctx), caseworker = ctxCaseworker(ctx),
                        attempts = attempt, responseChars = result.length(),
                        durationMs = elapsedMs(started));
                return {body: {response: result, session_id: body.session_id}};
            }
            lastErr = result;

            if state.mutated {
                log:printError("chat.retry.suppressed", cause = errSummary(result),
                        requestId = ctx.requestId, attempt = attempt,
                        detail = "attempt already wrote to the case store — not retrying, a " +
                                "replay could duplicate a note");
                break;
            }
            if attempt < MAX_ATTEMPTS {
                decimal backoff = RETRY_BACKOFF_SECONDS * <decimal>attempt;
                log:printWarn("chat.attempt.failed", cause = errSummary(result),
                        requestId = ctx.requestId, attempt = attempt, maxAttempts = MAX_ATTEMPTS,
                        backoffSeconds = backoff);
                runtime:sleep(backoff);
            }
        }

        log:printError("chat.request.degraded",
                cause = lastErr is error ? errSummary(lastErr) : NONE,
                requestId = ctx.requestId, session = ctxSession(ctx),
                maxAttempts = MAX_ATTEMPTS, durationMs = elapsedMs(started));
        // The full error object, once, at DEBUG — for whoever is actually diagnosing this.
        // Keeping it off the ERROR line is what stops a third party's response headers and
        // cookies from landing in the default log stream.
        log:printDebug("chat.request.degraded.detail", 'error = lastErr, requestId = ctx.requestId);
        return {body: {response: DEGRADED_MESSAGE, session_id: body.session_id}};
    }

    // Test-only escape hatch, carried over from the MCP twin's /debug/mcpCall. It calls any
    // named tool directly, bypassing the LLM, so a test can prove the *gate* refuses the four
    // ungranted tools — not merely that the prompt never offers them. Deliberately not
    // retry/degrade-wrapped: a test needs the raw refusal text, not a friendly fallback.
    isolated resource function post debug/toolCall(http:Request req, @http:Payload DebugToolRequest body)
            returns DebugToolOk {
        ReqCtx ctx = newReqCtx("POST /debug/toolCall", ());
        string? oboToken = extractOboToken(req, {message: ""});
        log:printInfo("debug.toolcall.received", requestId = ctx.requestId, tool = body.tool,
                args = redactArgs(body.arguments), oboPresented = oboToken is string);

        ToolOutcome|error outcome = invokeTool(ctx, body.tool, body.arguments, oboToken);
        if outcome is error {
            return {body: {isError: true, text: errSummary(outcome)}};
        }
        return {body: {isError: outcome.isError, text: outcome.text}};
    }
}
