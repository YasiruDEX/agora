// Logging conventions for this agent.
//
// Every log line in this package follows the same two rules, so the output is greppable and
// machine-parseable without a bespoke parser:
//
//   1. The message is a dotted *event name*, never a sentence — `tool.invoke.denied`,
//      `db.notes.decrypt.failed`, `chat.llm.turn`. Human explanation goes in a `detail`
//      key-value, not in the message.
//   2. Every line emitted while serving a request carries `requestId` (and `caseworker`
//      once known), so a single conversation can be reconstructed with
//      `grep requestId=<id>`.
//
// Level policy (this is the contract the rest of the package is written against):
//
//   DEBUG  Mechanics an operator only wants when actively diagnosing: each SQL access with
//          row counts, each LLM turn, tool arguments (redacted), per-step latency.
//   INFO   The normal request lifecycle and startup: request received/completed, tool
//          invoked/completed, schema init, seed summary, listener up.
//   WARN   Something was refused or degraded but the agent handled it and kept serving:
//          missing/unknown on-behalf-of token, out-of-scope tool attempt, case-ownership
//          denial, a retried attempt, step budget exhausted.
//   ERROR  The request could not be served as asked: DB failure, LLM failure, decrypt
//          failure, exhausted retries.
//
// A policy denial is a WARN, not an ERROR: it means the security boundary did its job.
// Reserve ERROR for "this agent is not working", so that alerting on ERROR stays meaningful.
//
// Set the level at runtime with `LOG_LEVEL=DEBUG ./run.sh` (run.sh maps it to Ballerina's
// `BAL_CONFIG_VAR_BALLERINA_LOG_LEVEL`), or in Config.toml — see Config.toml.example.
// Ballerina's `log` module is doing the formatting, so `format = "json"` in Config.toml
// switches the whole package to structured JSON output with no code change.
import ballerina/lang.value;
import ballerina/log;
import ballerina/time;
import ballerina/uuid;

// Per-request correlation context, threaded through every function that logs. `caseworker`
// starts as () and is filled in once the on-behalf-of token has been introspected — so
// pre-auth lines are still correlated by requestId even though the identity isn't known yet.
type ReqCtx record {|
    string requestId;
    string route;
    string? sessionId;
    string? caseworkerId;
|};

isolated function newReqCtx(string route, string? sessionId) returns ReqCtx {
    // Short id: long enough to be unique within a session's logs, short enough to read.
    string raw = uuid:createType4AsString();
    return {requestId: raw.substring(0, 8), route, sessionId, caseworkerId: ()};
}

// Placeholder for an absent value, so a log line never renders `key=` or `key=null` and
// every line has the same shape whether or not the field is known yet.
const string NONE = "-";

isolated function ctxSession(ReqCtx ctx) returns string => ctx.sessionId ?: NONE;

isolated function ctxCaseworker(ReqCtx ctx) returns string => ctx.caseworkerId ?: NONE;

// Elapsed milliseconds since `startedAt` (from `time:monotonicNow()`), rounded to 1dp so
// latency fields stay readable.
isolated function elapsedMs(decimal startedAt) returns decimal {
    decimal seconds = time:monotonicNow() - startedAt;
    return (<decimal>(<int>(seconds * 10000.0d))) / 10.0d;
}

// Truncate free text before it reaches a log line. Case notes and citizen-supplied text can
// contain PII, and a caseworker's note is not something to spill into an operator's log
// aggregator in full — logs get the shape and size of the value, not the value.
isolated function redact(string value, int keep = 48) returns string {
    string trimmed = value.trim();
    if trimmed.length() <= keep {
        return trimmed;
    }
    return trimmed.substring(0, keep) + string `…(+${trimmed.length() - keep} chars)`;
}

// Tool arguments go to DEBUG logs, but `note` bodies are caseworker-authored prose — keep the
// keys and sizes, redact the values.
isolated function redactArgs(map<json> args) returns string {
    string[] parts = [];
    foreach [string, json] [key, value] in args.entries() {
        string rendered = value is string ? redact(value) : value.toJsonString();
        parts.push(string `${key}=${rendered}`);
    }
    return parts.length() == 0 ? "{}" : string:'join(" ", ...parts);
}

// Secrets must never reach a log line, but "is it set, and does it look right?" is the single
// most useful thing at startup — so log the shape, never the value.
isolated function fingerprint(string secret) returns string {
    if secret == "" {
        return "<unset>";
    }
    return string `<set:${secret.length()} chars>`;
}

isolated function logStartup(string event, string detail) {
    log:printInfo(event, detail = detail);
}

// Collapse an error into one short line for a WARN/ERROR key-value.
//
// This exists because passing an error straight to log:print* via `'error = e` serialises the
// whole detail record, and for an HTTP client error that means the full response: every
// response header, the `set-cookie` value, and a base64 body — thousands of characters, three
// times over across retries, burying the one fact an operator needs. Worse, it writes a
// third party's Set-Cookie into the log.
//
// So the default-level line gets message + status + cause, capped; the raw error is logged
// separately at DEBUG where someone is already digging and nothing is buried.
isolated function errSummary(error err) returns string {
    string summary = err.message();

    // OpenAPI-generated clients (ballerinax/openai.chat) and ballerina/http put the status
    // code in the error detail — the single most useful field, and cheap to lift out.
    value:Cloneable? status = err.detail()["statusCode"];
    if status is int {
        summary += string ` (status ${status})`;
    }

    error? cause = err.cause();
    if cause is error {
        summary += string ` <- ${cause.message()}`;
    }
    return redact(summary, 240);
}
