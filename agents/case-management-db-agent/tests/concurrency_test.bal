// Concurrency tests.
//
// The /chat, /health and /debug/toolCall resource methods are declared `isolated`, which is
// what lets Ballerina serve them in parallel — without it the runtime serialises every
// request, and one caseworker's two-second LLM turn blocks every other caseworker. Marking a
// method isolated is a promise, so these tests exercise it: several caseworkers hitting the
// store at once must not corrupt each other's results, lose a write, or trip SQLITE_BUSY.
//
// The embedded store deliberately runs a single JDBC connection (see store.bal), so writes
// queue rather than race. That is the property under test here — queuing, not failing.
import ballerina/test;

@test:Config {groups: ["concurrency", "identity"]}
function testConcurrentSearchesDoNotLeakAcrossCaseworkers() returns error? {
    // The failure this guards against is the worst one possible for this agent: two
    // caseworkers in flight simultaneously, and one of them seeing the other's cases.
    future<CaseRow[]|error>[] pending = [];
    foreach int i in 0 ..< 12 {
        string caseworker = i % 2 == 0 ? "joan.ellis" : "renee.alvarez";
        future<CaseRow[]|error> pendingSearch = start searchCases(testCtx(string `c${i}`), caseworker, "");
        pending.push(pendingSearch);
    }

    foreach int i in 0 ..< pending.length() {
        string expected = i % 2 == 0 ? "joan.ellis" : "renee.alvarez";
        CaseRow[] cases = check wait pending[i];
        test:assertEquals(cases.length(), 3, string `request ${i} got the wrong number of cases`);
        foreach CaseRow c in cases {
            test:assertEquals(c.assigned_caseworker_id, expected,
                    string `request ${i} for ${expected} returned a case owned by ${c.assigned_caseworker_id}`);
        }
    }
}

@test:Config {groups: ["concurrency"]}
function testConcurrentWritesAllLandExactlyOnce() returns error? {
    // Every note must persist, with no lost update and no duplicate — and no SQLITE_BUSY,
    // which is what the single-connection pool is there to prevent.
    ReqCtx ctx = testCtx("cw");
    int before = (check listNotes(ctx, "CASE-1005")).length();

    future<CaseNote|error>[] pending = [];
    foreach int i in 0 ..< 10 {
        future<CaseNote|error> pendingWrite = start addNote(ctx, "CASE-1005", "Renee Alvarez",
                string `Concurrent write ${i}.`);
        pending.push(pendingWrite);
    }
    foreach future<CaseNote|error> f in pending {
        CaseNote written = check wait f;
        test:assertTrue(written.noteId > 0);
    }

    CaseNote[] after = check listNotes(ctx, "CASE-1005");
    test:assertEquals(after.length(), before + 10, "every concurrent write must persist once");

    // Each note body appears exactly once.
    foreach int i in 0 ..< 10 {
        string expected = string `Concurrent write ${i}.`;
        int matches = 0;
        foreach CaseNote note in after {
            if note.content == expected {
                matches += 1;
            }
        }
        test:assertEquals(matches, 1, string `'${expected}' persisted ${matches} times`);
    }
}

@test:Config {groups: ["concurrency", "encryption"]}
function testConcurrentEncryptionProducesDistinctIvs() returns error? {
    // A shared or repeated IV across concurrent calls would mean identical plaintexts
    // producing identical ciphertexts — the randomBytes source has to be safe under
    // parallelism, not just sequentially.
    future<string|error>[] pending = [];
    foreach int _ in 0 ..< 24 {
        future<string|error> pendingEncrypt = start fernetEncrypt("identical plaintext");
        pending.push(pendingEncrypt);
    }

    string[] tokens = [];
    foreach future<string|error> f in pending {
        string token = check wait f;
        test:assertTrue(tokens.indexOf(token) is (), "two concurrent encryptions collided");
        tokens.push(token);
        test:assertEquals(check fernetDecrypt(token), "identical plaintext");
    }
}

@test:Config {groups: ["concurrency", "identity"]}
function testConcurrentToolInvocationsKeepTheirOwnIdentity() returns error? {
    // Each request carries its own ReqCtx, so the caseworker recorded for correlation must
    // not bleed between in-flight requests.
    future<ToolOutcome|error>[] pending = [];
    ReqCtx[] contexts = [];
    foreach int i in 0 ..< 10 {
        ReqCtx ctx = testCtx(string `ci${i}`);
        contexts.push(ctx);
        future<ToolOutcome|error> pendingCall =
                start invokeTool(ctx, "case_search", {}, i % 2 == 0 ? JOAN_TOKEN : RENEE_TOKEN);
        pending.push(pendingCall);
    }

    foreach int i in 0 ..< pending.length() {
        ToolOutcome outcome = check wait pending[i];
        test:assertFalse(outcome.isError);
        string expectedName = i % 2 == 0 ? "Joan Ellis" : "Renee Alvarez";
        map<json> payload = check (check outcome.text.fromJsonString()).ensureType();
        test:assertEquals(payload["caseworker"], expectedName);
        test:assertEquals(contexts[i].caseworkerId,
                i % 2 == 0 ? "joan.ellis" : "renee.alvarez",
                string `request ${i} recorded the wrong caseworker on its context`);
    }
}
