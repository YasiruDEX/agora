// Logging-helper tests.
//
// These are cheap but not ceremonial: redact() and fingerprint() are the only things standing
// between a caseworker's case notes (or the encryption key) and an operator's log aggregator,
// and the correlation id is what makes a request traceable at all. A regression in any of
// them is a privacy or debuggability problem that no other test would catch.
import ballerina/test;

@test:Config {groups: ["observability"]}
function testRedactKeepsShortValuesIntact() {
    test:assertEquals(redact("open"), "open");
    test:assertEquals(redact("  padded  "), "padded");
    test:assertEquals(redact(""), "");
}

@test:Config {groups: ["observability"]}
function testRedactTruncatesLongValuesAndReportsWhatItDropped() {
    string note = "Home visit completed. Needs assessment scored at 62 hours/month pending sign-off.";
    string redacted = redact(note);
    test:assertTrue(redacted.length() < note.length());
    test:assertTrue(redacted.startsWith("Home visit completed."));
    test:assertTrue(redacted.includes("chars)"),
            "the reader needs to know something was dropped, and how much");
    test:assertFalse(redacted.includes("sign-off"), "the tail must not survive redaction");
}

@test:Config {groups: ["observability"]}
function testRedactHonoursAnExplicitBudget() {
    test:assertTrue(redact("abcdefghij", 4).startsWith("abcd"));
    test:assertEquals(redact("abcdefghij", 100), "abcdefghij");
}

@test:Config {groups: ["observability"]}
function testRedactArgsKeepsKeysAndRedactsValues() {
    string rendered = redactArgs({
        "case_id": "CASE-1001",
        "note": "Client disclosed a new address and a change in household income this month.",
        "count": 3
    });
    test:assertTrue(rendered.includes("case_id=CASE-1001"), rendered);
    test:assertTrue(rendered.includes("count=3"), "non-string arguments stay legible");
    test:assertTrue(rendered.includes("note=Client disclosed"), rendered);
    test:assertFalse(rendered.includes("household income"),
            "a long note body must be truncated in logs");
}

@test:Config {groups: ["observability"]}
function testRedactArgsHandlesNoArguments() {
    test:assertEquals(redactArgs({}), "{}");
}

@test:Config {groups: ["observability"]}
function testFingerprintNeverRevealsTheSecret() {
    string key = "V1KMEbNn7hbwsUyoIWzk3fRlZeMxaBLGyQCbdWLmYnE=";
    string printed = fingerprint(key);
    test:assertFalse(printed.includes(key), "the whole point is that the value never appears");
    test:assertFalse(printed.includes(key.substring(0, 8)), "not even a prefix");
    test:assertTrue(printed.includes(key.length().toString()),
            "length is what makes 'is it set correctly?' answerable at a glance");
    test:assertEquals(fingerprint(""), "<unset>");
}

@test:Config {groups: ["observability"]}
function testRequestIdsAreShortAndUnique() {
    string[] seen = [];
    foreach int _ in 0 ..< 50 {
        ReqCtx ctx = newReqCtx("POST /chat", ());
        test:assertEquals(ctx.requestId.length(), 8, "ids are read by humans in a terminal");
        test:assertTrue(seen.indexOf(ctx.requestId) is (),
                string `duplicate request id ${ctx.requestId} — correlation would be ambiguous`);
        seen.push(ctx.requestId);
    }
}

@test:Config {groups: ["observability"]}
function testContextRendersAbsentFieldsAsAPlaceholder() {
    // Absent fields must render as "-" rather than empty, so every log line has the same
    // shape and a key never appears with nothing after it.
    ReqCtx empty = newReqCtx("POST /chat", ());
    test:assertEquals(ctxSession(empty), NONE);
    test:assertEquals(ctxCaseworker(empty), NONE);

    ReqCtx withSession = newReqCtx("POST /chat", "s-joan-1");
    test:assertEquals(ctxSession(withSession), "s-joan-1");
}

@test:Config {groups: ["observability"]}
function testElapsedMsIsNonNegativeAndRounded() {
    decimal elapsed = elapsedMs(0d);
    test:assertTrue(elapsed >= 0d);
    // One decimal place: latency in logs should be readable, not a 9-digit fraction.
    test:assertEquals(elapsed * 10d, decimal:round(elapsed * 10d));
}

@test:Config {groups: ["observability"]}
function testErrSummaryKeepsTheMessageAndStatus() {
    // Shape of what ballerinax/openai.chat raises on a 401.
    error httpish = error("Unauthorized", statusCode = 401, headers = {"set-cookie": "secret=1"});
    string summary = errSummary(httpish);
    test:assertTrue(summary.includes("Unauthorized"), summary);
    test:assertTrue(summary.includes("status 401"), summary);
}

@test:Config {groups: ["observability"]}
function testErrSummaryDropsTheResponseDetail() {
    // The regression this guards: an unsummarised error serialises its whole detail record,
    // which for an HTTP error means every response header — including Set-Cookie — landing in
    // the log at WARN and ERROR, three times over across retries.
    error httpish = error("Unauthorized",
            statusCode = 401,
            headers = {"set-cookie": "__cf_bm=SHOULD-NOT-BE-LOGGED", "cf-ray": "abc123"},
            body = "{\"error\": {\"message\": \"Incorrect API key provided\"}}");
    string summary = errSummary(httpish);
    test:assertFalse(summary.includes("SHOULD-NOT-BE-LOGGED"),
            string `a Set-Cookie value reached the log line: ${summary}`);
    test:assertFalse(summary.includes("cf-ray"), summary);
    test:assertTrue(summary.length() <= 260, string `summary is ${summary.length()} chars: ${summary}`);
}

@test:Config {groups: ["observability"]}
function testErrSummaryIncludesTheCause() {
    error root = error("Connection refused");
    error wrapped = error("SQL execute failed", root);
    string summary = errSummary(wrapped);
    test:assertTrue(summary.includes("SQL execute failed"), summary);
    test:assertTrue(summary.includes("Connection refused"),
            string `the root cause is the useful half: ${summary}`);
}

@test:Config {groups: ["observability"]}
function testErrSummaryIsCappedForVerboseErrors() {
    string huge = "";
    foreach int _ in 0 ..< 500 {
        huge += "0123456789";
    }
    string summary = errSummary(error(huge));
    test:assertTrue(summary.length() <= 260, string `summary is ${summary.length()} chars`);
}
