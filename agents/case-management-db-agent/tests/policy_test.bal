// Policy-gate tests: tool scope and on-behalf-of identity.
//
// These are the tests that would have to be written against the MCP server in the MCP twin.
// Since this agent enforces both boundaries itself, they are unit-testable here — which is
// the practical argument for the no-MCP variant: the security boundary is covered by the same
// `bal test` run as the rest of the agent, with no second process to stand up.
import ballerina/test;

function testCtx(string label) returns ReqCtx =>
    {requestId: label, route: "test", sessionId: (), caseworkerId: ()};

final Caseworker JOAN = {caseworker_id: "joan.ellis", name: "Joan Ellis"};

const string JOAN_TOKEN = "obo_joan_ellis_4a7c9f";
const string RENEE_TOKEN = "obo_renee_alvarez_1e6b2d";

// --- the scope declaration itself ------------------------------------------------------------

@test:Config {groups: ["policy", "scope"]}
function testGrantedToolsAreASubsetOfAllTools() {
    foreach string granted in GRANTED_TOOLS {
        test:assertTrue(ALL_TOOLS.indexOf(granted) != (),
                string `'${granted}' is granted but not declared in ALL_TOOLS`);
    }
    test:assertEquals(GRANTED_TOOLS.length(), 3);
    test:assertEquals(ALL_TOOLS.length(), 7);
}

@test:Config {groups: ["policy", "scope"]}
function testToolSpecsCoverExactlyAllTools() {
    // TOOL_SPECS is the single source of truth for the tool surface; if the two ever diverge,
    // a tool could be offered to the model without a scope entry, or gated without existing.
    string[] declared = from ToolSpec spec in TOOL_SPECS
        select spec.name;
    foreach string name in ALL_TOOLS {
        test:assertTrue(declared.indexOf(name) != (),
                string `'${name}' is in ALL_TOOLS but has no TOOL_SPECS entry`);
    }
    foreach string name in declared {
        test:assertTrue(isKnownTool(name),
                string `TOOL_SPECS declares '${name}', which is not in ALL_TOOLS`);
    }
    test:assertEquals(declared.length(), ALL_TOOLS.length());
}

@test:Config {groups: ["policy", "scope"]}
function testModelIsOfferedExactlyTheGrantedTools() {
    // The first of the two scope layers: what the LLM can even ask for. Derived from
    // GRANTED_TOOLS, and asserted here so a hand-edit to either can't silently widen it.
    string[] offered = from var tool in chatTools
        select tool.'function.name;
    string[] granted = from string name in GRANTED_TOOLS
        select name;
    test:assertEquals(offered.sort(), granted.sort());
    foreach string ungranted in ["case_status_update", "citizen_profile_read",
            "citizen_profile_write", "case_close"] {
        test:assertTrue(offered.indexOf(ungranted) is (),
                string `'${ungranted}' must never be offered to the model`);
    }
}

@test:Config {groups: ["policy", "scope"]}
function testEveryDeclaredToolHasAnImplementation() {
    // The second layer only means something if the gated functions exist. Called with empty
    // arguments and a case id that cannot match, so nothing is mutated: any tool reached here
    // refuses on a missing argument or a missing record, and none returns the dispatcher's
    // "No implementation wired" error.
    foreach ToolSpec spec in TOOL_SPECS {
        ToolOutcome|error outcome = dispatchTool(testCtx("dispatch"), spec.name, {}, JOAN);
        if outcome is error {
            test:assertFail(string `'${spec.name}' has no implementation: ${outcome.message()}`);
        }
        test:assertFalse(outcome.text.includes("No implementation wired"),
                string `'${spec.name}' fell through the dispatcher`);
    }
}

// --- layer 2: the gate ------------------------------------------------------------------------

@test:Config {groups: ["policy", "scope"]}
function testUngrantedToolsAreDeniedWithAValidToken() returns error? {
    // A valid caseworker token is not enough: scope is checked first and independently, so
    // these are refused even though the caller is fully authenticated.
    foreach string ungranted in ["case_status_update", "citizen_profile_read",
            "citizen_profile_write", "case_close"] {
        ToolOutcome outcome = check invokeTool(testCtx("scope"), ungranted,
                {"case_id": "CASE-1001", "citizen_id": "CIT-3001", "new_status": "closed"},
                JOAN_TOKEN);
        test:assertTrue(outcome.isError, string `'${ungranted}' was not refused`);
        test:assertTrue(outcome.text.includes("Tool scope violation"),
                string `'${ungranted}' was refused for the wrong reason: ${outcome.text}`);
        test:assertTrue(outcome.text.includes("Denied before reaching the store"));
    }
}

@test:Config {groups: ["policy", "scope"]}
function testScopeIsCheckedBeforeIdentity() returns error? {
    // Ordering matters for the message the caseworker sees: an ungranted tool with no token
    // must report the scope violation, not the missing token, because widening the token
    // would not help.
    ToolOutcome outcome = check invokeTool(testCtx("order"), "case_close",
            {"case_id": "CASE-1001"}, ());
    test:assertTrue(outcome.text.includes("Tool scope violation"), outcome.text);
}

@test:Config {groups: ["policy"]}
function testUnknownToolIsRejected() returns error? {
    ToolOutcome outcome = check invokeTool(testCtx("unknown"), "drop_everything", {}, JOAN_TOKEN);
    test:assertTrue(outcome.isError);
    test:assertTrue(outcome.text.includes("Unknown tool"), outcome.text);
}

// --- on-behalf-of identity --------------------------------------------------------------------

@test:Config {groups: ["policy", "identity"]}
function testIntrospectionResolvesKnownTokens() {
    Caseworker? joan = introspect(JOAN_TOKEN);
    Caseworker? renee = introspect(RENEE_TOKEN);
    test:assertEquals(joan?.caseworker_id, "joan.ellis");
    test:assertEquals(renee?.caseworker_id, "renee.alvarez");
}

@test:Config {groups: ["policy", "identity"]}
function testIntrospectionRejectsInactiveTokens() {
    // "Inactive", in RFC 7662 terms: absent, blank, or unrecognised all resolve to no
    // identity — never to a default or fallback caseworker.
    test:assertTrue(introspect(()) is ());
    test:assertTrue(introspect("") is ());
    test:assertTrue(introspect("   ") is ());
    test:assertTrue(introspect("obo_not_a_real_token") is ());
    test:assertTrue(introspect(JOAN_TOKEN + "x") is (), "token matching must be exact");
}

@test:Config {groups: ["policy", "identity"]}
function testGrantedToolsRequireAnIdentity() returns error? {
    foreach string granted in GRANTED_TOOLS {
        ToolOutcome outcome = check invokeTool(testCtx("noauth"), granted,
                {"case_id": "CASE-1001", "note": "x"}, ());
        test:assertTrue(outcome.isError, string `'${granted}' ran without an identity`);
        test:assertTrue(outcome.text.includes("on-behalf-of token"), outcome.text);
    }
}

@test:Config {groups: ["policy", "identity"]}
function testAuthorizeRecordsTheCaseworkerOnTheRequestContext() {
    // The correlation context has to pick up the identity, or the audit trail for a request
    // loses track of who it was acting for halfway through.
    ReqCtx ctx = testCtx("ctx");
    test:assertTrue(ctx.caseworkerId is ());
    Caseworker|ToolOutcome authorized = authorizeTool(ctx, "case_search", JOAN_TOKEN);
    test:assertTrue(authorized is Caseworker);
    test:assertEquals(ctx.caseworkerId, "joan.ellis");
    test:assertEquals(ctxCaseworker(ctx), "joan.ellis");
}

@test:Config {groups: ["policy", "identity"]}
function testFailedAuthorizationLeavesTheContextUnattributed() {
    ReqCtx ctx = testCtx("ctx-denied");
    Caseworker|ToolOutcome authorized = authorizeTool(ctx, "case_search", "obo_bogus");
    test:assertTrue(authorized is ToolOutcome);
    test:assertTrue(ctx.caseworkerId is ());
    test:assertEquals(ctxCaseworker(ctx), NONE);
}

// --- retry safety -----------------------------------------------------------------------------

@test:Config {groups: ["policy"]}
function testEveryMutatingToolIsMarkedAsSuch() {
    // MUTATING_TOOLS drives retry suppression in /chat. A write missing from this list would
    // be silently replayed on a retry, duplicating a caseworker's note.
    foreach string tool in ["case_notes_write", "case_status_update", "citizen_profile_write",
            "case_close"] {
        test:assertTrue(MUTATING_TOOLS.indexOf(tool) != (),
                string `'${tool}' writes to the store but is not in MUTATING_TOOLS`);
    }
    foreach string tool in ["case_search", "case_read"] {
        test:assertTrue(MUTATING_TOOLS.indexOf(tool) is (),
                string `'${tool}' is read-only and should stay retryable`);
    }
}
