// Configuration for the Case Management DB Agent.
//
// This is the no-MCP twin of ../case-management-agent: identical /chat contract, identical
// governance story (tool scope + on-behalf-of identity), but the case database is reached
// directly from inside the agent through its own Ballerina tools instead of over MCP. So the
// config surface differs in exactly two ways from the MCP twin:
//
//   - gone:  MCP_SERVER_URL and the four AMP_AGENTID_* vars. There is no outbound MCP call,
//            therefore no MCP proxy to mint an AgentID access token for.
//   - added: CASEMGMT_DB_PATH / CASEMGMT_ENCRYPTION_KEY / CASEMGMT_SEED_DIR. The agent now
//            owns the encrypted store the MCP server used to own.
import ballerina/log;
import ballerina/os;

// AM's chat-agent interface is always POST /chat on port 8000, and AM's build-time
// OpenAPI/server generation has to resolve the port *statically* — a port computed from
// os:getEnv(...) fails that build step with "Unsupported expression found for the server port
// value". So this stays a `configurable`, and the only supported override is
// BAL_CONFIG_VAR_PORT=<port> (not PORT). See README.
configurable int port = 8000;

final string countyName = envOr("COUNTY_NAME", "Riverside County");
final string openAiApiKey = envOr("OPENAI_API_KEY", "");
final string openAiModel = envOr("OPENAI_MODEL", "gpt-4o-mini");

// Embedded SQLite store (PLAN.md §6). Default is this agent's own copy under data/, seeded
// from seed/*.json on startup, so the agent runs with nothing else alive. Point
// CASEMGMT_DB_PATH at mcp-servers/case-management-mcp-server/data/case_mgmt.db to run
// against the MCP twin's database instead — the on-disk format is byte-compatible (same
// schema, same Fernet field encryption), which is what makes the two agents genuinely
// comparable rather than merely similar.
final string dbPath = envOr("CASEMGMT_DB_PATH", "data/case_mgmt.db");
final string seedDir = envOr("CASEMGMT_SEED_DIR", "seed");
final boolean seedOnStart = envOr("CASEMGMT_SEED_ON_START", "true").toLowerAscii() == "true";

// Field-level encryption key for citizen PII and case-note content — a security boundary, so
// it is required with no fallback. Same Fernet key format the MCP twin uses
// (base64url-encoded 32 bytes); generate one with:
//   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
final string encryptionKeyB64 = check requireEnv("CASEMGMT_ENCRYPTION_KEY");

// --- Tool scope -----------------------------------------------------------------------------
// With MCP gone, nothing outside this process enforces which tools the agent may use — so the
// scope gate moves inside, and stays a gate rather than becoming a naming convention. The
// agent implements all seven case-system operations (an admin tool with a broader grant needs
// them to exist) but is *granted* three. GRANTED_TOOLS is what the LLM is offered AND what
// authorizeTool() enforces; the other four are denied before any SQL runs, and the denial is
// logged. Two independent layers, same as the MCP twin: the model is never offered a tool it
// cannot use, and a call that arrives anyway is still refused.
final readonly & string[] ALL_TOOLS = [
    "case_search",
    "case_read",
    "case_notes_write",
    "case_status_update",
    "citizen_profile_read",
    "citizen_profile_write",
    "case_close"
];

final readonly & string[] GRANTED_TOOLS = ["case_search", "case_read", "case_notes_write"];

isolated function isKnownTool(string name) returns boolean => ALL_TOOLS.indexOf(name) != ();

isolated function isGrantedTool(string name) returns boolean => GRANTED_TOOLS.indexOf(name) != ();

// --- On-behalf-of identity ------------------------------------------------------------------
// Opaque token -> caseworker identity. Stands in for the county IDP issuing tokens the agent
// introspects via RFC 7662 (PLAN.md §8); in the MCP twin the MCP server did this introspection,
// here the agent does it itself. Field names are snake_case to match the MCP twin's
// CASEMGMT_OBO_TOKENS_JSON payload verbatim, so the same override value works for both.
type Caseworker record {|
    string caseworker_id;
    string name;
|};

final readonly & map<Caseworker> DEFAULT_OBO_TOKENS = {
    "obo_joan_ellis_4a7c9f": {caseworker_id: "joan.ellis", name: "Joan Ellis"},
    "obo_renee_alvarez_1e6b2d": {caseworker_id: "renee.alvarez", name: "Renee Alvarez"}
};

final readonly & map<Caseworker> oboTokens = check loadOboTokens();

function loadOboTokens() returns (readonly & map<Caseworker>)|error {
    string raw = os:getEnv("CASEMGMT_OBO_TOKENS_JSON").trim();
    if raw == "" {
        return DEFAULT_OBO_TOKENS;
    }
    json parsed = check raw.fromJsonString();
    map<Caseworker> loaded = check parsed.cloneWithType();
    log:printInfo("config.obo.loaded", origin = "CASEMGMT_OBO_TOKENS_JSON", count = loaded.length());
    return loaded.cloneReadOnly();
}

// RFC 7662-style introspection stand-in: an active token maps to a caseworker identity, an
// absent or unknown one is "inactive" and resolves to ().
isolated function introspect(string? token) returns Caseworker? {
    if token is () || token.trim() == "" {
        return ();
    }
    return oboTokens[token];
}

// --- Resilience knobs -----------------------------------------------------------------------
// A transport/infrastructure failure (DB locked, LLM unreachable) is retried before the
// caseworker sees anything; a policy denial is not retried, because retrying a refusal just
// refuses again more slowly.
final int MAX_ATTEMPTS = 3;
final decimal RETRY_BACKOFF_SECONDS = 1.0d;
final int MAX_LLM_TURNS = 5;

final string DEGRADED_MESSAGE =
    "I'm sorry, I can't get to the case system right now. This isn't something you did " +
    "wrong; please try again in a moment, or use the case management system directly if it " +
    "keeps happening.";

// --- env helpers ----------------------------------------------------------------------------

function envOr(string name, string fallback) returns string {
    string val = os:getEnv(name);
    return val.trim() == "" ? fallback : val;
}

function requireEnv(string name) returns string|error {
    string val = os:getEnv(name);
    if val.trim() == "" {
        return error(string `Missing required env var: ${name}`);
    }
    return val.trim();
}
