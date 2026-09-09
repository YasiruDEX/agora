// Encrypted-at-rest case store — embedded SQLite, reached directly from inside the agent.
//
// This is the file that replaces MCP. In ../case-management-agent every one of these
// operations was a network round trip to a Python MCP server; here each is a local SQL
// statement over an embedded database file, and the agent's tools call these functions
// in-process.
//
// The schema and the field-level Fernet encryption match
// ../../mcp-servers/case-management-mcp-server/store.py exactly, so the two agents can share
// one database file. Two details make that true rather than approximately true:
//
//   - encrypted columns are read back with CAST(col AS TEXT), because a Fernet token is
//     ASCII and the column is a BLOB;
//   - encrypted columns are *written* as byte[], not string. SQLite is dynamically typed, so
//     binding a string would store TEXT — and Python's store does `Fernet.decrypt(bytes(v))`,
//     which raises TypeError on a str. Writing bytes keeps rows this agent creates readable
//     by the Python server.
//
// Concurrency: SQLite serialises writers, so the pool is capped at one connection rather
// than letting concurrent requests race into SQLITE_BUSY. The store is embedded and the
// statements are single-row lookups, so the queue is not the bottleneck — the LLM call is.
import ballerina/file;
import ballerina/log;
import ballerina/sql;
import ballerina/time;
import ballerinax/java.jdbc;

// Row shapes mirror the SQL columns (snake_case) so `query`/`queryRow` can map them directly.
type CaseRow record {|
    string case_id;
    string citizen_id;
    string case_type;
    string status;
    string assigned_caseworker_id;
    string summary;
    float opened_at;
    float updated_at;
|};

type NoteRow record {|
    int note_id;
    string case_id;
    string author;
    // Fernet token, read via CAST(content_enc AS TEXT).
    string content_enc;
    float created_at;
|};

type CitizenRow record {|
    string citizen_id;
    string full_name_enc;
    string date_of_birth_enc;
    string ssn_last4_enc;
    string address_enc;
    string phone_enc;
    string email_enc;
    int household_size;
    string notes_enc;
|};

// Decrypted domain types — what the tools actually hand back to the model.
type CaseNote record {|
    int noteId;
    string caseId;
    string author;
    string content;
    float createdAt;
|};

type CitizenProfile record {|
    string citizenId;
    string fullName;
    string dateOfBirth;
    string ssnLast4;
    string address;
    string phone;
    string email;
    int householdSize;
    string notes;
|};

final jdbc:Client dbClient = check newDbClient();

function newDbClient() returns jdbc:Client|error {
    check ensureParentDir(dbPath);
    return new (url = string `jdbc:sqlite:${dbPath}`, connectionPool = {maxOpenConnections: 1});
}

function ensureParentDir(string path) returns error? {
    string parent = check file:parentPath(check file:getAbsolutePath(path));
    if !check file:test(parent, file:EXISTS) {
        check file:createDir(parent, file:RECURSIVE);
        log:printInfo("db.dir.created", path = parent);
    }
}

isolated function initSchema() returns error? {
    decimal started = time:monotonicNow();
    // Each DDL statement is passed straight to execute() rather than collected into a
    // `sql:ParameterizedQuery[]` first: the ballerina/sql compiler plugin inspects query
    // templates at their call site, and templates held in an array make it fail the build
    // with "Symbol is 'null'". SQLite's JDBC driver also runs one statement per execute, so
    // there is nothing to batch here anyway.
    _ = check dbClient->execute(`CREATE TABLE IF NOT EXISTS citizen_profiles (
        citizen_id TEXT PRIMARY KEY,
        full_name_enc BLOB NOT NULL,
        date_of_birth_enc BLOB NOT NULL,
        ssn_last4_enc BLOB NOT NULL,
        address_enc BLOB NOT NULL,
        phone_enc BLOB NOT NULL,
        email_enc BLOB NOT NULL,
        household_size INTEGER NOT NULL,
        notes_enc BLOB NOT NULL
    )`);
    _ = check dbClient->execute(`CREATE TABLE IF NOT EXISTS cases (
        case_id TEXT PRIMARY KEY,
        citizen_id TEXT NOT NULL,
        case_type TEXT NOT NULL,
        status TEXT NOT NULL,
        assigned_caseworker_id TEXT NOT NULL,
        summary TEXT NOT NULL,
        opened_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )`);
    _ = check dbClient->execute(`CREATE TABLE IF NOT EXISTS case_notes (
        note_id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id TEXT NOT NULL,
        author TEXT NOT NULL,
        content_enc BLOB NOT NULL,
        created_at REAL NOT NULL
    )`);
    // Not in the Python schema, and safe to add: case_search always filters by caseworker,
    // and this is the difference between a scan and a lookup once the table is real-sized.
    _ = check dbClient->execute(`CREATE INDEX IF NOT EXISTS idx_cases_caseworker ON cases (assigned_caseworker_id)`);
    _ = check dbClient->execute(`CREATE INDEX IF NOT EXISTS idx_case_notes_case ON case_notes (case_id)`);

    log:printInfo("db.schema.ready", path = dbPath, durationMs = elapsedMs(started));
}

// --- cases ----------------------------------------------------------------------------------

// Filtering happens in Ballerina, not SQL, deliberately: it reproduces the MCP twin's
// substring-match semantics exactly (case-insensitive `in` against case_type, summary, and
// status) without a LIKE pattern that would also have to escape %/_ out of the caseworker's
// own query text. The caseworker-scoped result set is a handful of rows, so the cost is nil.
isolated function searchCases(ReqCtx ctx, string caseworkerId, string query) returns CaseRow[]|error {
    decimal started = time:monotonicNow();
    stream<CaseRow, sql:Error?> rs = dbClient->query(
        `SELECT case_id, citizen_id, case_type, status, assigned_caseworker_id, summary,
                opened_at, updated_at
           FROM cases
          WHERE assigned_caseworker_id = ${caseworkerId}
          ORDER BY updated_at DESC`);
    CaseRow[] assigned = check from CaseRow row in rs
        select row;

    string term = query.trim().toLowerAscii();
    CaseRow[] matched = term == "" ? assigned : from CaseRow c in assigned
        where c.case_type.toLowerAscii().includes(term)
            || c.summary.toLowerAscii().includes(term)
            || c.status.toLowerAscii().includes(term)
        select c;

    log:printDebug("db.cases.search", requestId = ctx.requestId, caseworker = caseworkerId,
            term = term == "" ? NONE : redact(term), assigned = assigned.length(),
            matched = matched.length(), durationMs = elapsedMs(started));
    return matched;
}

isolated function readCaseRow(ReqCtx ctx, string caseId) returns CaseRow?|error {
    decimal started = time:monotonicNow();
    CaseRow|sql:Error row = dbClient->queryRow(
        `SELECT case_id, citizen_id, case_type, status, assigned_caseworker_id, summary,
                opened_at, updated_at
           FROM cases WHERE case_id = ${caseId}`);
    if row is sql:NoRowsError {
        log:printDebug("db.cases.read.miss", requestId = ctx.requestId, caseId = caseId,
                durationMs = elapsedMs(started));
        return ();
    }
    if row is sql:Error {
        return row;
    }
    log:printDebug("db.cases.read.hit", requestId = ctx.requestId, caseId = caseId,
            status = row.status, durationMs = elapsedMs(started));
    return row;
}

isolated function updateCaseStatus(ReqCtx ctx, string caseId, string newStatus) returns CaseRow?|error {
    if check readCaseRow(ctx, caseId) is () {
        return ();
    }
    decimal now = <decimal>time:utcNow()[0];
    _ = check dbClient->execute(
        `UPDATE cases SET status = ${newStatus}, updated_at = ${now} WHERE case_id = ${caseId}`);
    log:printInfo("db.cases.status.updated", requestId = ctx.requestId, caseId = caseId,
            newStatus = newStatus);
    return readCaseRow(ctx, caseId);
}

// --- case notes -----------------------------------------------------------------------------

isolated function listNotes(ReqCtx ctx, string caseId) returns CaseNote[]|error {
    decimal started = time:monotonicNow();
    stream<NoteRow, sql:Error?> rs = dbClient->query(
        `SELECT note_id, case_id, author, CAST(content_enc AS TEXT) AS content_enc, created_at
           FROM case_notes WHERE case_id = ${caseId} ORDER BY created_at ASC`);
    NoteRow[] rows = check from NoteRow row in rs
        select row;

    CaseNote[] notes = [];
    foreach NoteRow row in rows {
        string|error content = fernetDecrypt(row.content_enc);
        if content is error {
            // One unreadable row must not take down the whole case read: surface it as a
            // placeholder the model can relay honestly, and log it at ERROR because a
            // decrypt failure means a key/data mismatch an operator has to fix.
            log:printError("db.notes.decrypt.failed", cause = errSummary(content),
                    requestId = ctx.requestId, caseId = caseId, noteId = row.note_id);
            notes.push({
                noteId: row.note_id,
                caseId: row.case_id,
                author: row.author,
                content: "(note content unavailable — could not be decrypted)",
                createdAt: row.created_at
            });
            continue;
        }
        notes.push({
            noteId: row.note_id,
            caseId: row.case_id,
            author: row.author,
            content: content,
            createdAt: row.created_at
        });
    }
    log:printDebug("db.notes.list", requestId = ctx.requestId, caseId = caseId,
            count = notes.length(), durationMs = elapsedMs(started));
    return notes;
}

isolated function addNote(ReqCtx ctx, string caseId, string author, string content) returns CaseNote|error {
    decimal started = time:monotonicNow();
    decimal now = <decimal>time:utcNow()[0];
    // byte[], not string — see the file header: keeps the row readable by the Python store.
    byte[] encrypted = (check fernetEncrypt(content)).toBytes();

    sql:ExecutionResult result = check dbClient->execute(
        `INSERT INTO case_notes (case_id, author, content_enc, created_at)
         VALUES (${caseId}, ${author}, ${encrypted}, ${now})`);
    // A note is the case's most recent activity, so it moves the case up in case_search.
    _ = check dbClient->execute(`UPDATE cases SET updated_at = ${now} WHERE case_id = ${caseId}`);

    int noteId = result.lastInsertId is int ? <int>result.lastInsertId : 0;
    log:printInfo("db.notes.written", requestId = ctx.requestId, caseId = caseId, author = author,
            noteId = noteId, contentChars = content.length(), durationMs = elapsedMs(started));
    return {noteId: noteId, caseId: caseId, author: author, content: content, createdAt: <float>now};
}

isolated function countNotes(string caseId) returns int|error {
    return dbClient->queryRow(`SELECT COUNT(*) FROM case_notes WHERE case_id = ${caseId}`);
}

// --- citizen profiles -----------------------------------------------------------------------
// Reachable only through the four tools this agent is *not* granted; kept because the store
// has to be complete for an admin identity with a broader grant, and because it gives
// authorizeTool() something real to refuse.

isolated function readCitizen(ReqCtx ctx, string citizenId) returns CitizenProfile?|error {
    CitizenRow|sql:Error row = dbClient->queryRow(
        `SELECT citizen_id,
                CAST(full_name_enc AS TEXT) AS full_name_enc,
                CAST(date_of_birth_enc AS TEXT) AS date_of_birth_enc,
                CAST(ssn_last4_enc AS TEXT) AS ssn_last4_enc,
                CAST(address_enc AS TEXT) AS address_enc,
                CAST(phone_enc AS TEXT) AS phone_enc,
                CAST(email_enc AS TEXT) AS email_enc,
                household_size,
                CAST(notes_enc AS TEXT) AS notes_enc
           FROM citizen_profiles WHERE citizen_id = ${citizenId}`);
    if row is sql:NoRowsError {
        return ();
    }
    if row is sql:Error {
        return row;
    }
    log:printDebug("db.citizens.read", requestId = ctx.requestId, citizenId = citizenId);
    return {
        citizenId: row.citizen_id,
        fullName: check fernetDecrypt(row.full_name_enc),
        dateOfBirth: check fernetDecrypt(row.date_of_birth_enc),
        ssnLast4: check fernetDecrypt(row.ssn_last4_enc),
        address: check fernetDecrypt(row.address_enc),
        phone: check fernetDecrypt(row.phone_enc),
        email: check fernetDecrypt(row.email_enc),
        householdSize: row.household_size,
        notes: check fernetDecrypt(row.notes_enc)
    };
}

// Read-merge-write, matching the Python store's update_citizen_fields: only the keys present
// in `fields` change, everything else is re-encrypted as-is. household_size is not editable
// through this path in either implementation.
isolated function updateCitizenFields(ReqCtx ctx, string citizenId, map<string> fields)
        returns CitizenProfile?|error {
    CitizenProfile? existing = check readCitizen(ctx, citizenId);
    if existing is () {
        return ();
    }
    check upsertCitizen({
        citizenId: existing.citizenId,
        fullName: fields["full_name"] ?: existing.fullName,
        dateOfBirth: fields["date_of_birth"] ?: existing.dateOfBirth,
        ssnLast4: fields["ssn_last4"] ?: existing.ssnLast4,
        address: fields["address"] ?: existing.address,
        phone: fields["phone"] ?: existing.phone,
        email: fields["email"] ?: existing.email,
        householdSize: existing.householdSize,
        notes: fields["notes"] ?: existing.notes
    });
    log:printInfo("db.citizens.updated", requestId = ctx.requestId, citizenId = citizenId,
            fields = fields.keys().toString());
    return readCitizen(ctx, citizenId);
}

isolated function upsertCitizen(CitizenProfile profile) returns error? {
    // Encrypt into locals first: the ballerina/sql compiler plugin type-checks every
    // interpolation, and a `check` expression inside the template makes it fail with
    // "Symbol is 'null'". Hoisting is also clearer about what is encrypted and what isn't
    // (household_size stays plaintext, matching the Python schema).
    byte[] fullName = (check fernetEncrypt(profile.fullName)).toBytes();
    byte[] dateOfBirth = (check fernetEncrypt(profile.dateOfBirth)).toBytes();
    byte[] ssnLast4 = (check fernetEncrypt(profile.ssnLast4)).toBytes();
    byte[] address = (check fernetEncrypt(profile.address)).toBytes();
    byte[] phone = (check fernetEncrypt(profile.phone)).toBytes();
    byte[] email = (check fernetEncrypt(profile.email)).toBytes();
    byte[] notes = (check fernetEncrypt(profile.notes)).toBytes();

    _ = check dbClient->execute(
        `INSERT INTO citizen_profiles
            (citizen_id, full_name_enc, date_of_birth_enc, ssn_last4_enc, address_enc,
             phone_enc, email_enc, household_size, notes_enc)
         VALUES (${profile.citizenId}, ${fullName}, ${dateOfBirth}, ${ssnLast4}, ${address},
                 ${phone}, ${email}, ${profile.householdSize}, ${notes})
         ON CONFLICT(citizen_id) DO UPDATE SET
            full_name_enc = excluded.full_name_enc,
            date_of_birth_enc = excluded.date_of_birth_enc,
            ssn_last4_enc = excluded.ssn_last4_enc,
            address_enc = excluded.address_enc,
            phone_enc = excluded.phone_enc,
            email_enc = excluded.email_enc,
            household_size = excluded.household_size,
            notes_enc = excluded.notes_enc`);
}

isolated function upsertCase(CaseRow row) returns error? {
    _ = check dbClient->execute(
        `INSERT INTO cases
            (case_id, citizen_id, case_type, status, assigned_caseworker_id, summary,
             opened_at, updated_at)
         VALUES (${row.case_id}, ${row.citizen_id}, ${row.case_type}, ${row.status},
                 ${row.assigned_caseworker_id}, ${row.summary}, ${row.opened_at},
                 ${row.updated_at})
         ON CONFLICT(case_id) DO UPDATE SET
            citizen_id = excluded.citizen_id,
            case_type = excluded.case_type,
            status = excluded.status,
            assigned_caseworker_id = excluded.assigned_caseworker_id,
            summary = excluded.summary`);
}
