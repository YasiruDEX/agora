// The agent's own tools, and the policy gate in front of them.
//
// In the MCP twin these three tools lived on a remote MCP server, and *that server* enforced
// tool scope and on-behalf-of identity. With MCP gone, both boundaries move in here — the
// point of this variant is that they move, not that they disappear:
//
//   1. Tool scope. TOOL_SPECS declares all seven case-system operations; GRANTED_TOOLS names
//      the three this agent's identity holds. `chatTools()` derives the LLM's tool list from
//      that intersection, so the model is never offered a tool it cannot use, and
//      `authorizeTool()` refuses the other four before any SQL runs, so a call that arrives
//      by some other path is still denied. Deriving both from one table is what stops the
//      prompt and the gate from drifting apart.
//   2. On-behalf-of identity. Every tool call must carry a token that introspects to a
//      caseworker; results are then restricted to that caseworker's own assigned cases.
//      Ownership is re-checked per case_id, so a case belonging to another caseworker is
//      *denied*, not merely absent from search results.
//
// Return-type contract, which the retry logic in main.bal depends on:
//
//   ToolOutcome{isError: false}  the tool ran
//   ToolOutcome{isError: true}   a policy decision or a missing record — an expected answer,
//                                fed back to the model verbatim so it can explain the real
//                                reason. Never retried; retrying a refusal just refuses again.
//   error                        infrastructure failed (SQL error, decrypt failure). Retried,
//                                then degraded to a plain-language apology.
//
// The JSON payloads are byte-identical in shape to the MCP twin's tool results, so the system
// prompt, the model's behaviour, and any downstream evaluator carry over unchanged.
import ballerina/log;
import ballerina/time;

import ballerinax/openai.chat;

type ToolOutcome record {|
    boolean isError;
    string text;
|};

type ToolSpec record {|
    string name;
    string description;
    map<json> parameters;
|};

// Single source of truth for the tool surface. All seven are declared; only the granted ones
// are ever handed to the model or accepted by the gate.
final readonly & ToolSpec[] TOOL_SPECS = [
    {
        name: "case_search",
        description: "Search the on-behalf-of caseworker's own assigned cases. Pass an empty query to list all of them, or a keyword to filter by case type, status, or summary text.",
        parameters: {"type": "object", "properties": {"query": {"type": "string"}}, "required": []}
    },
    {
        name: "case_read",
        description: "Read full details of a case, including its notes. Only cases assigned to the on-behalf-of caseworker are readable.",
        parameters: {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]}
    },
    {
        name: "case_notes_write",
        description: "Add a note to one of the on-behalf-of caseworker's own assigned cases.",
        parameters: {
            "type": "object",
            "properties": {"case_id": {"type": "string"}, "note": {"type": "string"}},
            "required": ["case_id", "note"]
        }
    },
    {
        name: "case_status_update",
        description: "Update a case's status. Outside this agent's granted tool scope.",
        parameters: {
            "type": "object",
            "properties": {"case_id": {"type": "string"}, "new_status": {"type": "string"}},
            "required": ["case_id", "new_status"]
        }
    },
    {
        name: "citizen_profile_read",
        description: "Read a citizen's full profile, including PII. Outside this agent's granted tool scope.",
        parameters: {"type": "object", "properties": {"citizen_id": {"type": "string"}}, "required": ["citizen_id"]}
    },
    {
        name: "citizen_profile_write",
        description: "Update a citizen's profile fields. Outside this agent's granted tool scope.",
        parameters: {"type": "object", "properties": {"citizen_id": {"type": "string"}}, "required": ["citizen_id"]}
    },
    {
        name: "case_close",
        description: "Close a case. Outside this agent's granted tool scope.",
        parameters: {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]}
    }
];

// What the LLM is offered: the granted subset, derived — never hand-listed a second time.
// Readonly so the isolated request path can read it without a lock.
final readonly & chat:ChatCompletionTool[] chatTools = buildChatTools();

isolated function buildChatTools() returns readonly & chat:ChatCompletionTool[] {
    chat:ChatCompletionTool[] tools = from ToolSpec spec in TOOL_SPECS
        where isGrantedTool(spec.name)
        select {
            'type: "function",
            'function: {name: spec.name, description: spec.description, parameters: spec.parameters}
        };
    return <readonly & chat:ChatCompletionTool[]>tools.cloneReadOnly();
}

// --- policy gate ----------------------------------------------------------------------------

isolated function denied(string text) returns ToolOutcome => {isError: true, text: text};

// Returns the introspected caseworker on success, or the refusal to hand back to the model.
isolated function authorizeTool(ReqCtx ctx, string toolName, string? oboToken) returns Caseworker|ToolOutcome {
    if !isKnownTool(toolName) {
        log:printWarn("tool.unknown", requestId = ctx.requestId, tool = toolName);
        return denied(string `Unknown tool '${toolName}'.`);
    }

    if !isGrantedTool(toolName) {
        // WARN, not ERROR: the boundary worked. This is the line that proves the scope gate
        // is real, so it names both the attempted tool and the grant it was measured against.
        log:printWarn("tool.scope.denied", requestId = ctx.requestId, tool = toolName,
                grantedScope = GRANTED_TOOLS.toString(),
                detail = "denied before reaching the store");
        return denied(string `Tool scope violation: '${toolName}' is not in this agent's ` +
                string `granted tool scope (${string:'join(", ", ...GRANTED_TOOLS)}). ` +
                string `Denied before reaching the store.`);
    }

    Caseworker? caseworker = introspect(oboToken);
    if caseworker is () {
        log:printWarn("auth.obo.denied", requestId = ctx.requestId, tool = toolName,
                presented = oboToken is string ? "unknown-token" : "absent");
        return denied("Access denied: missing or inactive on-behalf-of token. This agent " +
                "requires a valid X-OBO-Token identifying the caseworker.");
    }

    ctx.caseworkerId = caseworker.caseworker_id;
    log:printDebug("auth.obo.ok", requestId = ctx.requestId, tool = toolName,
            caseworker = caseworker.caseworker_id);
    return caseworker;
}

// Ownership is enforced per case_id, not just via the search filter — otherwise a caseworker
// who learned another caseworker's case_id could read it directly.
isolated function requireOwnCase(ReqCtx ctx, Caseworker caseworker, string caseId) returns CaseRow|ToolOutcome|error {
    CaseRow? row = check readCaseRow(ctx, caseId);
    if row is () {
        return denied(string `No case found for case_id '${caseId}'.`);
    }
    if row.assigned_caseworker_id != caseworker.caseworker_id {
        log:printWarn("auth.case.ownership.denied", requestId = ctx.requestId, caseId = caseId,
                caseworker = caseworker.caseworker_id, assignedTo = row.assigned_caseworker_id);
        return denied(string `Access denied: case '${caseId}' is not assigned to ${caseworker.name}.`);
    }
    return row;
}

// --- dispatch -------------------------------------------------------------------------------

isolated function invokeTool(ReqCtx ctx, string toolName, map<json> args, string? oboToken) returns ToolOutcome|error {
    decimal started = time:monotonicNow();
    log:printInfo("tool.invoke.start", requestId = ctx.requestId, session = ctxSession(ctx),
            tool = toolName, args = redactArgs(args));

    Caseworker|ToolOutcome authorized = authorizeTool(ctx, toolName, oboToken);
    if authorized is ToolOutcome {
        log:printInfo("tool.invoke.refused", requestId = ctx.requestId, tool = toolName,
                durationMs = elapsedMs(started));
        return authorized;
    }

    ToolOutcome|error outcome = dispatchTool(ctx, toolName, args, authorized);
    if outcome is error {
        log:printError("tool.invoke.failed", cause = errSummary(outcome),
                requestId = ctx.requestId, tool = toolName,
                caseworker = authorized.caseworker_id, durationMs = elapsedMs(started));
        log:printDebug("tool.invoke.failed.detail", 'error = outcome, requestId = ctx.requestId);
        return outcome;
    }
    log:printInfo("tool.invoke.done", requestId = ctx.requestId, tool = toolName,
            caseworker = authorized.caseworker_id, refused = outcome.isError,
            resultChars = outcome.text.length(), durationMs = elapsedMs(started));
    return outcome;
}

// Every tool in TOOL_SPECS is implemented here, granted or not — same shape as the MCP twin's
// server, which also implements all seven and lets `_authorize` do the refusing. Keeping the
// four ungranted ones real and working is the point: what stops `case_close` is this agent's
// grant, not a missing function. Nothing reaches this dispatcher without having cleared
// authorizeTool() first, so `caseworker` is always an introspected identity.
isolated function dispatchTool(ReqCtx ctx, string toolName, map<json> args, Caseworker caseworker)
        returns ToolOutcome|error {
    match toolName {
        "case_search" => {
            return caseSearch(ctx, caseworker, stringArg(args, "query") ?: "");
        }
        "case_read" => {
            string? caseId = stringArg(args, "case_id");
            if caseId is () {
                return denied("case_read requires a 'case_id' argument.");
            }
            return caseRead(ctx, caseworker, caseId);
        }
        "case_notes_write" => {
            string? caseId = stringArg(args, "case_id");
            string? note = stringArg(args, "note");
            if caseId is () || note is () {
                return denied("case_notes_write requires both a 'case_id' and a 'note' argument.");
            }
            return caseNotesWrite(ctx, caseworker, caseId, note);
        }
        "case_status_update" => {
            string? caseId = stringArg(args, "case_id");
            string? newStatus = stringArg(args, "new_status");
            if caseId is () || newStatus is () {
                return denied("case_status_update requires both a 'case_id' and a 'new_status' argument.");
            }
            return caseStatusUpdate(ctx, caseworker, caseId, newStatus);
        }
        "case_close" => {
            string? caseId = stringArg(args, "case_id");
            if caseId is () {
                return denied("case_close requires a 'case_id' argument.");
            }
            return caseStatusUpdate(ctx, caseworker, caseId, "closed");
        }
        "citizen_profile_read" => {
            string? citizenId = stringArg(args, "citizen_id");
            if citizenId is () {
                return denied("citizen_profile_read requires a 'citizen_id' argument.");
            }
            return citizenProfileRead(ctx, citizenId);
        }
        "citizen_profile_write" => {
            string? citizenId = stringArg(args, "citizen_id");
            if citizenId is () {
                return denied("citizen_profile_write requires a 'citizen_id' argument.");
            }
            return citizenProfileWrite(ctx, citizenId, args);
        }
    }
    // Unreachable while TOOL_SPECS and this match stay in step — tests/policy_test.bal fails
    // the build if a declared tool ever has no implementation behind it.
    return error(string `No implementation wired for tool '${toolName}'`);
}

isolated function stringArg(map<json> args, string name) returns string? {
    json? value = args[name];
    if value is string {
        return value;
    }
    return ();
}

// --- the three granted tools -----------------------------------------------------------------

isolated function caseSearch(ReqCtx ctx, Caseworker caseworker, string query) returns ToolOutcome|error {
    CaseRow[] cases = check searchCases(ctx, caseworker.caseworker_id, query);
    json payload = {
        caseworker: caseworker.name,
        query: query,
        results: from CaseRow c in cases
            select {
                case_id: c.case_id,
                citizen_id: c.citizen_id,
                case_type: c.case_type,
                status: c.status,
                summary: c.summary,
                updated_at: c.updated_at
            }
    };
    return {isError: false, text: payload.toJsonString()};
}

isolated function caseRead(ReqCtx ctx, Caseworker caseworker, string caseId) returns ToolOutcome|error {
    CaseRow|ToolOutcome|error owned = requireOwnCase(ctx, caseworker, caseId);
    if owned is ToolOutcome|error {
        return owned;
    }
    CaseNote[] notes = check listNotes(ctx, caseId);
    json payload = {
        case_id: owned.case_id,
        citizen_id: owned.citizen_id,
        case_type: owned.case_type,
        status: owned.status,
        summary: owned.summary,
        opened_at: owned.opened_at,
        updated_at: owned.updated_at,
        notes: from CaseNote n in notes
            select {author: n.author, content: n.content, created_at: n.createdAt}
    };
    return {isError: false, text: payload.toJsonString()};
}

isolated function caseNotesWrite(ReqCtx ctx, Caseworker caseworker, string caseId, string note)
        returns ToolOutcome|error {
    CaseRow|ToolOutcome|error owned = requireOwnCase(ctx, caseworker, caseId);
    if owned is ToolOutcome|error {
        return owned;
    }
    if note.trim() == "" {
        return denied("case_notes_write requires a non-empty note.");
    }
    // Authored by the introspected caseworker, never by whoever the model claims — the note's
    // author is an identity fact, not a model output.
    CaseNote written = check addNote(ctx, caseId, caseworker.name, note);
    json payload = {
        case_id: written.caseId,
        author: written.author,
        content: written.content,
        created_at: written.createdAt,
        status: "written"
    };
    return {isError: false, text: payload.toJsonString()};
}

// --- the four tools outside this agent's grant ------------------------------------------------
// Real implementations, unreachable through this agent: authorizeTool() refuses all four
// before dispatch. They exist because the store has to be complete for an admin identity with
// a broader grant, and because a scope gate guarding functions that don't exist proves
// nothing.

isolated function caseStatusUpdate(ReqCtx ctx, Caseworker caseworker, string caseId, string newStatus)
        returns ToolOutcome|error {
    CaseRow|ToolOutcome|error owned = requireOwnCase(ctx, caseworker, caseId);
    if owned is ToolOutcome|error {
        return owned;
    }
    CaseRow? updated = check updateCaseStatus(ctx, caseId, newStatus);
    if updated is () {
        return denied(string `No case found for case_id '${caseId}'.`);
    }
    return {isError: false, text: {case_id: updated.case_id, status: updated.status}.toJsonString()};
}

isolated function citizenProfileRead(ReqCtx ctx, string citizenId) returns ToolOutcome|error {
    CitizenProfile? profile = check readCitizen(ctx, citizenId);
    if profile is () {
        return denied(string `No citizen profile found for citizen_id '${citizenId}'.`);
    }
    json payload = {
        citizen_id: profile.citizenId,
        full_name: profile.fullName,
        date_of_birth: profile.dateOfBirth,
        ssn_last4: profile.ssnLast4,
        address: profile.address,
        phone: profile.phone,
        email: profile.email,
        household_size: profile.householdSize,
        notes: profile.notes
    };
    return {isError: false, text: payload.toJsonString()};
}

isolated function citizenProfileWrite(ReqCtx ctx, string citizenId, map<json> args) returns ToolOutcome|error {
    map<string> fields = {};
    foreach string key in ["full_name", "address", "phone", "email", "notes"] {
        string? value = stringArg(args, key);
        if value is string {
            fields[key] = value;
        }
    }
    CitizenProfile? updated = check updateCitizenFields(ctx, citizenId, fields);
    if updated is () {
        return denied(string `No citizen profile found for citizen_id '${citizenId}'.`);
    }
    return {isError: false, text: {citizen_id: updated.citizenId, status: "updated"}.toJsonString()};
}
