// Store and tool-behaviour tests against a real SQLite database.
//
// test.sh points CASEMGMT_DB_PATH at a throwaway file and wipes it first, so these run
// against a genuine embedded database rather than a mock — the encryption, the SQL, and the
// BLOB round trip are all exercised for real. Seeding is idempotent, so calling it here is
// safe even though the service's init() has already run.
import ballerina/test;

@test:BeforeSuite
function prepareStore() returns error? {
    check initSchema();
    check seedAll();
}

// --- caseworker isolation ---------------------------------------------------------------------

@test:Config {groups: ["store", "identity"]}
function testSearchReturnsOnlyTheCaseworkersOwnCases() returns error? {
    CaseRow[] joans = check searchCases(testCtx("s1"), "joan.ellis", "");
    CaseRow[] renees = check searchCases(testCtx("s2"), "renee.alvarez", "");

    test:assertEquals(joans.length(), 3);
    test:assertEquals(renees.length(), 3);
    foreach CaseRow c in joans {
        test:assertEquals(c.assigned_caseworker_id, "joan.ellis");
    }
    foreach CaseRow c in renees {
        test:assertEquals(c.assigned_caseworker_id, "renee.alvarez");
    }

    // The two result sets must not overlap at all — this is the property the demo turns on.
    string[] joanIds = from CaseRow c in joans
        select c.case_id;
    foreach CaseRow c in renees {
        test:assertTrue(joanIds.indexOf(c.case_id) is (),
                string `${c.case_id} appeared in both caseworkers' results`);
    }
}

@test:Config {groups: ["store", "identity"]}
function testSearchForAnUnknownCaseworkerIsEmpty() returns error? {
    // Not an error and not everything: an unrecognised caseworker id must fail closed.
    CaseRow[] none = check searchCases(testCtx("s3"), "someone.else", "");
    test:assertEquals(none.length(), 0);
}

@test:Config {groups: ["store"]}
function testSearchFiltersByKeyword() returns error? {
    ReqCtx ctx = testCtx("s4");
    test:assertEquals((check searchCases(ctx, "joan.ellis", "calfresh")).length(), 1);
    test:assertEquals((check searchCases(ctx, "joan.ellis", "CALFRESH")).length(), 1,
            "matching is case-insensitive");
    test:assertEquals((check searchCases(ctx, "joan.ellis", "pending_review")).length(), 1,
            "status is searchable");
    test:assertEquals((check searchCases(ctx, "joan.ellis", "recertification")).length(), 1,
            "summary text is searchable");
    test:assertEquals((check searchCases(ctx, "joan.ellis", "nothing-matches-this")).length(), 0);
    test:assertEquals((check searchCases(ctx, "joan.ellis", "   ")).length(), 3,
            "a blank query lists everything, it does not match nothing");
}

@test:Config {groups: ["store"]}
function testSearchOrdersByMostRecentlyUpdated() returns error? {
    CaseRow[] cases = check searchCases(testCtx("s5"), "renee.alvarez", "");
    foreach int i in 1 ..< cases.length() {
        test:assertTrue(cases[i - 1].updated_at >= cases[i].updated_at,
                "case_search must return most-recently-updated first");
    }
}

// --- reads -------------------------------------------------------------------------------------

@test:Config {groups: ["store"]}
function testReadCaseHitAndMiss() returns error? {
    ReqCtx ctx = testCtx("r1");
    CaseRow? found = check readCaseRow(ctx, "CASE-1001");
    test:assertTrue(found is CaseRow);
    if found is CaseRow {
        test:assertEquals(found.case_type, "calworks");
        test:assertEquals(found.assigned_caseworker_id, "joan.ellis");
    }
    // A missing row is (), not an error — the tool layer turns it into a message the model
    // can relay, and an error here would trigger a pointless retry.
    test:assertTrue(check readCaseRow(ctx, "CASE-9999") is ());
}

@test:Config {groups: ["store", "encryption"]}
function testSeededNotesDecrypt() returns error? {
    CaseNote[] notes = check listNotes(testCtx("r2"), "CASE-1001");
    // The two seeded notes are asserted by position rather than by an exact total: other
    // tests in this suite append to cases, and a count assertion here would make this test
    // fail for reasons that have nothing to do with decryption.
    test:assertTrue(notes.length() >= 2, string `expected the 2 seeded notes, found ${notes.length()}`);
    test:assertTrue(notes[0].content.startsWith("Initial intake complete."),
            string `unexpected note content: ${notes[0].content}`);
    test:assertTrue(notes[1].content.startsWith("Client attended orientation."),
            string `unexpected note content: ${notes[1].content}`);
    foreach CaseNote note in notes {
        test:assertFalse(note.content.includes("could not be decrypted"));
        test:assertFalse(note.content.startsWith("gAAAAA"),
                "note content must be decrypted, not the raw Fernet token");
    }
}

@test:Config {groups: ["store"]}
function testNotesAreOrderedOldestFirst() returns error? {
    CaseNote[] notes = check listNotes(testCtx("r3"), "CASE-1001");
    foreach int i in 1 ..< notes.length() {
        test:assertTrue(notes[i - 1].createdAt <= notes[i].createdAt,
                "notes read as a chronology, so oldest must come first");
    }
}

@test:Config {groups: ["store", "encryption"]}
function testCitizenPiiDecrypts() returns error? {
    CitizenProfile? profile = check readCitizen(testCtx("r4"), "CIT-3001");
    test:assertTrue(profile is CitizenProfile);
    if profile is CitizenProfile {
        test:assertEquals(profile.fullName, "Elena Vasquez");
        test:assertEquals(profile.ssnLast4, "4471");
        test:assertEquals(profile.householdSize, 3);
    }
    test:assertTrue(check readCitizen(testCtx("r5"), "CIT-0000") is ());
}

// --- writes -------------------------------------------------------------------------------------

@test:Config {groups: ["store", "encryption"]}
function testNoteWriteRoundTripsThroughEncryption() returns error? {
    ReqCtx ctx = testCtx("w1");
    string content = "Round-trip check — Renée, 62 hours/month ✓";
    int before = (check listNotes(ctx, "CASE-1002")).length();

    CaseNote written = check addNote(ctx, "CASE-1002", "Joan Ellis", content);
    test:assertEquals(written.content, content);
    test:assertTrue(written.noteId > 0);

    CaseNote[] after = check listNotes(ctx, "CASE-1002");
    test:assertEquals(after.length(), before + 1);
    test:assertEquals(after[after.length() - 1].content, content,
            "the note must come back out of the database byte-identical");
    test:assertEquals(after[after.length() - 1].author, "Joan Ellis");
}

@test:Config {groups: ["store"]}
function testNoteWriteBumpsTheCaseUpdatedTimestamp() returns error? {
    ReqCtx ctx = testCtx("w2");
    CaseRow? before = check readCaseRow(ctx, "CASE-1003");
    _ = check addNote(ctx, "CASE-1003", "Joan Ellis", "Timestamp check.");
    CaseRow? after = check readCaseRow(ctx, "CASE-1003");

    if before is CaseRow && after is CaseRow {
        test:assertTrue(after.updated_at >= before.updated_at,
                "a new note is the case's latest activity, so it must move updated_at");
    } else {
        test:assertFail("CASE-1003 should exist");
    }
}

@test:Config {groups: ["store"]}
function testStatusUpdateAndMissingCase() returns error? {
    ReqCtx ctx = testCtx("w3");
    CaseRow? updated = check updateCaseStatus(ctx, "CASE-1006", "closed");
    test:assertEquals(updated?.status, "closed");
    test:assertTrue(check updateCaseStatus(ctx, "CASE-9999", "closed") is (),
            "updating a case that does not exist reports (), it does not create one");
}

@test:Config {groups: ["store", "encryption"]}
function testCitizenFieldUpdateMergesRatherThanReplaces() returns error? {
    ReqCtx ctx = testCtx("w4");
    CitizenProfile? updated = check updateCitizenFields(ctx, "CIT-3002", {"phone": "951-555-0999"});
    test:assertEquals(updated?.phone, "951-555-0999");
    // Everything not named in the update must survive, still encrypted and still readable.
    test:assertEquals(updated?.fullName, "Walter Briggs");
    test:assertEquals(updated?.ssnLast4, "8823");
    test:assertTrue(check updateCitizenFields(ctx, "CIT-0000", {"phone": "x"}) is ());
}

// --- ownership, at the tool layer ---------------------------------------------------------------

@test:Config {groups: ["store", "identity"]}
function testOwnershipIsEnforcedPerCaseId() returns error? {
    // Filtering search results is not sufficient on its own: a caseworker who learns another
    // caseworker's case_id must still be refused when reading it directly.
    ToolOutcome outcome = check invokeTool(testCtx("o1"), "case_read",
            {"case_id": "CASE-1004"}, JOAN_TOKEN);
    test:assertTrue(outcome.isError);
    test:assertTrue(outcome.text.includes("not assigned to Joan Ellis"), outcome.text);
}

@test:Config {groups: ["store", "identity"]}
function testWritesToAnotherCaseworkersCaseAreRefused() returns error? {
    ReqCtx ctx = testCtx("o2");
    int before = (check listNotes(ctx, "CASE-1004")).length();
    ToolOutcome outcome = check invokeTool(ctx, "case_notes_write",
            {"case_id": "CASE-1004", "note": "should not land"}, JOAN_TOKEN);
    test:assertTrue(outcome.isError);
    test:assertEquals((check listNotes(ctx, "CASE-1004")).length(), before,
            "a refused write must not have touched the store");
}

@test:Config {groups: ["store"]}
function testCaseSearchToolPayloadShape() returns error? {
    // The MCP twin's tool results have this exact shape, and the system prompt is written
    // against it — a change here silently changes what the model sees.
    ToolOutcome outcome = check invokeTool(testCtx("p1"), "case_search", {}, RENEE_TOKEN);
    test:assertFalse(outcome.isError);
    map<json> payload = check (check outcome.text.fromJsonString()).ensureType();
    test:assertEquals(payload["caseworker"], "Renee Alvarez");
    test:assertTrue(payload["results"] is json[]);
    json[] results = <json[]>payload["results"];
    test:assertEquals(results.length(), 3);
    map<json> first = check results[0].ensureType();
    foreach string fieldName in ["case_id", "citizen_id", "case_type", "status", "summary", "updated_at"] {
        test:assertTrue(first.hasKey(fieldName), string `case_search result is missing '${fieldName}'`);
    }
}

@test:Config {groups: ["store"]}
function testCaseReadToolPayloadIncludesNotes() returns error? {
    ToolOutcome outcome = check invokeTool(testCtx("p2"), "case_read",
            {"case_id": "CASE-1001"}, JOAN_TOKEN);
    test:assertFalse(outcome.isError);
    map<json> payload = check (check outcome.text.fromJsonString()).ensureType();
    test:assertEquals(payload["case_id"], "CASE-1001");
    test:assertTrue(payload["notes"] is json[]);
    map<json> note = check (<json[]>payload["notes"])[0].ensureType();
    foreach string fieldName in ["author", "content", "created_at"] {
        test:assertTrue(note.hasKey(fieldName), string `case_read note is missing '${fieldName}'`);
    }
}

@test:Config {groups: ["store"]}
function testMissingOrBlankArgumentsAreRefusedNotGuessed() returns error? {
    ReqCtx ctx = testCtx("a1");
    ToolOutcome noCaseId = check invokeTool(ctx, "case_read", {}, JOAN_TOKEN);
    test:assertTrue(noCaseId.isError);
    test:assertTrue(noCaseId.text.includes("requires a 'case_id'"), noCaseId.text);

    ToolOutcome noNote = check invokeTool(ctx, "case_notes_write",
            {"case_id": "CASE-1001"}, JOAN_TOKEN);
    test:assertTrue(noNote.isError);

    ToolOutcome blankNote = check invokeTool(ctx, "case_notes_write",
            {"case_id": "CASE-1001", "note": "   "}, JOAN_TOKEN);
    test:assertTrue(blankNote.isError);
    test:assertTrue(blankNote.text.includes("non-empty"), blankNote.text);
}

@test:Config {groups: ["store"]}
function testNoteAuthorComesFromTheTokenNotTheArguments() returns error? {
    // The author of a note is an identity fact. If the model could set it, the audit trail
    // would be worth nothing.
    ReqCtx ctx = testCtx("a2");
    // CASE-1002 rather than CASE-1001: the seeded-note assertions above read CASE-1001 by
    // position, and appending to it from here would couple the two tests together.
    ToolOutcome outcome = check invokeTool(ctx, "case_notes_write",
            {"case_id": "CASE-1002", "note": "Author attribution check.", "author": "Someone Else"},
            JOAN_TOKEN);
    test:assertFalse(outcome.isError);
    map<json> payload = check (check outcome.text.fromJsonString()).ensureType();
    test:assertEquals(payload["author"], "Joan Ellis");
}
