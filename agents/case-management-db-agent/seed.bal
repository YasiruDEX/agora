// Startup seeding from seed/*.json.
//
// The MCP twin got its data from the MCP server's own seeder; with the server gone this agent
// has to bring its own, or it starts up talking to an empty database. Same JSON files, same
// idempotency rules as ../../mcp-servers/case-management-mcp-server/seed_data.py:
//
//   - citizens and cases upsert by primary key, so a restart is a no-op;
//   - notes are append-only in real use, so a case that already has any notes is skipped
//     wholesale rather than re-inserting duplicates on every restart.
//
// Relative dates (`opened_days_ago`, `days_ago`) are resolved against startup time, which is
// what keeps the seeded cases looking recent no matter when the demo runs.
import ballerina/io;
import ballerina/log;
import ballerina/time;

const decimal SECONDS_PER_DAY = 86400.0d;

type CaseSeed record {|
    string case_id;
    string citizen_id;
    string case_type;
    string status;
    string assigned_caseworker_id;
    string summary;
    int opened_days_ago;
|};

type NoteSeed record {|
    string case_id;
    string author;
    string content;
    int days_ago;
|};

type CitizenSeed record {|
    string citizen_id;
    string full_name;
    string date_of_birth;
    string ssn_last4;
    string address;
    string phone;
    string email;
    int household_size;
    string notes = "";
|};

isolated function seedAll() returns error? {
    decimal started = time:monotonicNow();
    decimal now = <decimal>time:utcNow()[0];

    CitizenSeed[] citizens = check (check readSeedRows("citizen_profiles.json")).cloneWithType();
    foreach CitizenSeed c in citizens {
        check upsertCitizen({
            citizenId: c.citizen_id,
            fullName: c.full_name,
            dateOfBirth: c.date_of_birth,
            ssnLast4: c.ssn_last4,
            address: c.address,
            phone: c.phone,
            email: c.email,
            householdSize: c.household_size,
            notes: c.notes
        });
    }

    CaseSeed[] cases = check (check readSeedRows("cases.json")).cloneWithType();
    foreach CaseSeed c in cases {
        decimal openedAt = now - (<decimal>c.opened_days_ago * SECONDS_PER_DAY);
        check upsertCase({
            case_id: c.case_id,
            citizen_id: c.citizen_id,
            case_type: c.case_type,
            status: c.status,
            assigned_caseworker_id: c.assigned_caseworker_id,
            summary: c.summary,
            opened_at: <float>openedAt,
            updated_at: <float>openedAt
        });
    }

    NoteSeed[] notes = check (check readSeedRows("case_notes.json")).cloneWithType();
    string[] alreadyHasNotes = [];
    foreach CaseSeed c in cases {
        if check countNotes(c.case_id) > 0 {
            alreadyHasNotes.push(c.case_id);
        }
    }
    int seededNotes = 0;
    int skippedNotes = 0;
    ReqCtx seedCtx = {requestId: "seed", route: "startup", sessionId: (), caseworkerId: ()};
    foreach NoteSeed n in notes {
        if alreadyHasNotes.indexOf(n.case_id) != () {
            skippedNotes += 1;
            continue;
        }
        _ = check addNote(seedCtx, n.case_id, n.author, n.content);
        seededNotes += 1;
    }

    log:printInfo("seed.complete", citizens = citizens.length(), cases = cases.length(),
            notesWritten = seededNotes, notesSkipped = skippedNotes,
            durationMs = elapsedMs(started));
    if skippedNotes > 0 {
        log:printDebug("seed.notes.skipped", detail =
                string `${skippedNotes} seed note(s) skipped — their cases already had notes`,
                cases = alreadyHasNotes.toString());
    }
}

isolated function readSeedRows(string name) returns json[]|error {
    string path = string `${seedDir}/${name}`;
    json content = check io:fileReadJson(path);
    json[] rows = check content.ensureType();
    log:printDebug("seed.file.read", path = path, rows = rows.length());
    return rows;
}
