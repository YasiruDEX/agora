// Case Management Agent — Ballerina, native MCP client (PLAN.md §5, §7-8).
//
// Deliberately a different runtime than the two LangChain agents in this repo: proves that
// Agent Manager's governance layer (MCP scoping, on-behalf-of identity) applies identically
// regardless of what the agent is written in. This agent's LLM tool loop only ever wires in
// the 3 tools the Case Management Agent's identity is scoped into — case_search, case_read,
// case_notes_write. The other 4 tools the MCP server exposes are never offered to the model
// at all; /debug/mcp-call exists purely so a test script can prove that even a direct,
// deliberate attempt to call one of those 4 through this agent's own MCP connection is denied
// by the server, not just "not offered."
//
// Auth to the Case Management MCP proxy is OAuth2 client credentials (RFC 6749) with a
// resource indicator (RFC 8707), using the AgentID service account Agent Manager injects for
// this instance — the same pattern as the two Python agents (see mcp_tools.py in
// citizen-inquiry-agent / permit-licensing-agent). This is layered on top of, not instead of,
// the existing X-OBO-Token on-behalf-of caseworker header: OAuth2 proves *this agent
// instance's* identity to the platform, X-OBO-Token says *which caseworker* it's acting for
// right now — two independent boundaries, both still enforced.
import ballerina/http;
import ballerina/lang.runtime;
import ballerina/log;
import ballerina/os;
import ballerina/time;
import ballerina/url;

import ballerina/mcp;
import ballerinax/amp as _;
import ballerinax/openai.chat;

// AM's chat-agent interface is always POST /chat on port 8000 — this must be a literal/
// configurable expression (not computed from os:getEnv) so AM's build-time OpenAPI/server
// generation can statically resolve it. Override locally with BAL_CONFIG_VAR_PORT=<port> if
// you need a non-default port (e.g. running multiple agents side by side).
configurable int port = 8000;

final string countyName = osGetEnv("COUNTY_NAME", "Riverside County");
final string mcpServerUrl = osGetEnv("MCP_SERVER_URL", "http://127.0.0.1:8103/mcp");
final string openAiApiKey = osGetEnv("OPENAI_API_KEY", "");
final string openAiModel = osGetEnv("OPENAI_MODEL", "gpt-4o-mini");

// AgentID OAuth2 client-credentials — required, no local fallback (unlike the branding-only
// vars above, these are a security boundary and must come from Agent Manager or a real local
// test IDP).
final string agentidClientId = check requireEnv("AMP_AGENTID_CLIENT_ID");
final string agentidClientSecret = check requireEnv("AMP_AGENTID_CLIENT_SECRET");
final string agentidTokenEndpoint = check requireEnv("AMP_AGENTID_TOKEN_ENDPOINT");
final string agentidScopes = check requireEnv("AMP_AGENTID_SCOPES");

final int MAX_ATTEMPTS = 3;
final decimal RETRY_BACKOFF_SECONDS = 1.0d;
final decimal EXPIRY_SAFETY_MARGIN_SECONDS = 30.0d;
final decimal DEFAULT_ASSUMED_TTL_SECONDS = 60.0d;

final string TOOL_ACCESS_UNAVAILABLE_MESSAGE =
    "I'm sorry, I don't have access to that right now — one of my tools was denied by the " +
    "platform. This isn't something you did wrong; please try again in a moment, or contact " +
    "the department directly if it keeps happening.";

function osGetEnv(string name, string fallback) returns string {
    string val = os:getEnv(name);
    return val == "" ? fallback : val;
}

function requireEnv(string name) returns string|error {
    string val = os:getEnv(name);
    if val == "" {
        return error(string `Missing required env var: ${name}`);
    }
    return val;
}

final chat:Client openAiClient = check new ({auth: {token: openAiApiKey}});

// --- AgentID access token cache -------------------------------------------------------------
// Per-process cache keyed by MCP resource URL, expiry-aware (Ballerina equivalent of the
// Python agents' _TokenCache). Only one resource here (mcpServerUrl), but keying by URL keeps
// the shape consistent with permit-licensing-agent's multi-resource cache.

type TokenEntry record {|
    string token;
    decimal expiresAt;
|};

isolated map<TokenEntry> tokenCache = {};

function getAccessToken(string resourceUrl) returns string|error {
    decimal now = time:monotonicNow();
    lock {
        TokenEntry? cached = tokenCache[resourceUrl];
        if cached is TokenEntry && now < cached.expiresAt {
            return cached.token;
        }
    }
    [string, decimal] [freshToken, ttl] = check requestAccessToken(resourceUrl);
    decimal refreshedAt = time:monotonicNow();
    lock {
        tokenCache[resourceUrl] = {token: freshToken, expiresAt: refreshedAt + (ttl - EXPIRY_SAFETY_MARGIN_SECONDS)};
    }
    return freshToken;
}

function requestAccessToken(string resourceUrl) returns [string, decimal]|error {
    // Same h2c-upgrade hazard as the MCP client below: force HTTP/1.1 so this doesn't
    // intermittently fail against an HTTP/1.1-only token endpoint (e.g. a Python/uvicorn
    // AgentID stand-in during local testing).
    http:Client tokenClient = check new (agentidTokenEndpoint, httpVersion = http:HTTP_1_1);
    string basicAuth = (agentidClientId + ":" + agentidClientSecret).toBytes().toBase64();
    string encodedScope = check url:encode(agentidScopes, "UTF-8");
    string encodedResource = check url:encode(resourceUrl, "UTF-8");
    string formBody = string `grant_type=client_credentials&scope=${encodedScope}&resource=${encodedResource}`;

    http:Request tokenReq = new;
    tokenReq.setHeader("Authorization", "Basic " + basicAuth);
    tokenReq.setHeader("Content-Type", "application/x-www-form-urlencoded");
    tokenReq.setTextPayload(formBody);

    http:Response tokenResp = check tokenClient->post("", tokenReq);
    if tokenResp.statusCode != 200 {
        string errBody = "";
        string|error textPayload = tokenResp.getTextPayload();
        if textPayload is string {
            errBody = textPayload;
        }
        return error(string `AgentID token endpoint returned ${tokenResp.statusCode}: ${errBody}`);
    }

    map<json> payload = check (check tokenResp.getJsonPayload()).ensureType();
    string accessToken = check payload.get("access_token").ensureType(string);

    decimal ttl = DEFAULT_ASSUMED_TTL_SECONDS;
    json? expiresIn = payload["expires_in"];
    if expiresIn is int {
        ttl = <decimal>expiresIn;
    } else if expiresIn is float {
        ttl = <decimal>expiresIn;
    } else if expiresIn is decimal {
        ttl = expiresIn;
    }
    return [accessToken, ttl];
}

final chat:ChatCompletionTool[] SCOPED_TOOLS = [
    {
        'type: "function",
        'function: {
            name: "case_search",
            description: "Search the on-behalf-of caseworker's own assigned cases. Pass an empty query to list all of them, or a keyword to filter by case type, status, or summary text.",
            parameters: {"type": "object", "properties": {"query": {"type": "string"}}, "required": []}
        }
    },
    {
        'type: "function",
        'function: {
            name: "case_read",
            description: "Read full details of a case, including its notes. Only cases assigned to the on-behalf-of caseworker are readable.",
            parameters: {"type": "object", "properties": {"case_id": {"type": "string"}}, "required": ["case_id"]}
        }
    },
    {
        'type: "function",
        'function: {
            name: "case_notes_write",
            description: "Add a note to one of the on-behalf-of caseworker's own assigned cases.",
            parameters: {
                "type": "object",
                "properties": {"case_id": {"type": "string"}, "note": {"type": "string"}},
                "required": ["case_id", "note"]
            }
        }
    }
];

function buildSystemPrompt() returns string {
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

function mcpHeaders(string accessToken, string? oboToken) returns map<string|string[]> {
    // case-management-mcp-server (left unmodified, per design) only understands
    // X-MCP-API-Key — it doesn't have the "Authorization: Bearer <key>" fallback the other
    // three MCP servers in this repo support. Send the AgentID access token both ways: as
    // Authorization for a real OAuth2-validating proxy in front of it, and as X-MCP-API-Key
    // so this specific backend keeps working unmodified.
    map<string|string[]> headers = {
        "Authorization": "Bearer " + accessToken,
        "X-MCP-API-Key": accessToken
    };
    if oboToken is string {
        headers["X-OBO-Token"] = oboToken;
    }
    return headers;
}

function callMcpTool(string name, map<json> arguments, string? oboToken) returns mcp:CallToolResult|error {
    string accessToken = check getAccessToken(mcpServerUrl);

    // The Case Management MCP Server runs on Python/uvicorn (HTTP/1.1 only) — force HTTP/1.1
    // here, otherwise the default HTTP/2 client attempts an h2c upgrade uvicorn rejects
    // ("Unsupported upgrade request"), which surfaces as an intermittent transport error.
    mcp:StreamableHttpClient mcpClient = check new (mcpServerUrl, httpVersion = http:HTTP_1_1);
    check mcpClient->initialize({name: "case-management-agent", version: "0.1.0"}, {}, mcpHeaders(accessToken, oboToken));
    mcp:CallToolResult result = check mcpClient->callTool({name, arguments}, mcpHeaders(accessToken, oboToken));
    error? closeErr = mcpClient->close();
    if closeErr is error {
        log:printWarn("failed to close MCP client cleanly", 'error = closeErr);
    }
    return result;
}

function toolResultText(mcp:CallToolResult result) returns string {
    string[] parts = [];
    foreach mcp:ContentBlock block in result.content {
        if block is mcp:TextContent {
            parts.push(block.text);
        }
    }
    return string:'join("\n", ...parts);
}

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
|};

function extractOboToken(http:Request req, ChatRequest body) returns string? {
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

// Errors thrown by callMcpTool (transport failures: connection refused, unexpected non-2xx,
// a dead AgentID token endpoint) propagate out of this function via `check`, rather than being
// swallowed and turned into "ERROR: ..." tool-result text. In-band application errors (case
// not found, MCP scope denial, missing OBO token) are NOT Ballerina errors — the MCP server
// returns those as a normal CallToolResult with isError=true, which is still fed back to the
// model as before, since those are useful, expected responses to relay to the caseworker.
function runChatLoop(string userMessage, string? oboToken) returns string|error {
    chat:ChatCompletionRequestMessage[] messages = [
        {role: "system", content: buildSystemPrompt()},
        {role: "user", content: userMessage}
    ];

    int maxTurns = 5;
    foreach int _turn in 0 ..< maxTurns {
        chat:CreateChatCompletionRequest request = {
            model: openAiModel,
            messages,
            tools: SCOPED_TOOLS,
            temperature: 0
        };
        chat:CreateChatCompletionResponse response = check openAiClient->/chat/completions.post(request);
        if response.choices.length() == 0 {
            return "(no response)";
        }
        var choice = response.choices[0];
        chat:ChatCompletionResponseMessage assistantMsg = choice.message;
        chat:ChatCompletionMessageToolCalls? toolCalls = assistantMsg?.tool_calls;

        if toolCalls is () || toolCalls.length() == 0 {
            string? content = assistantMsg?.content;
            return content ?: "(no response)";
        }

        messages.push({
            role: "assistant",
            content: assistantMsg?.content,
            tool_calls: toolCalls
        });

        foreach chat:ChatCompletionMessageToolCall|chat:ChatCompletionMessageCustomToolCall call in toolCalls {
            if !(call is chat:ChatCompletionMessageToolCall) {
                continue;
            }
            string toolName = call.'function.name;
            json argsJson = {};
            json|error parsed = call.'function.arguments.fromJsonString();
            if parsed is json {
                argsJson = parsed;
            }
            map<json> argsMap = {};
            if argsJson is map<json> {
                argsMap = argsJson;
            }

            mcp:CallToolResult result = check callMcpTool(toolName, argsMap, oboToken);
            string toolResultContent;
            if result.isError == true {
                toolResultContent = string `ERROR: ${toolResultText(result)}`;
            } else {
                toolResultContent = toolResultText(result);
            }

            messages.push({
                role: "tool",
                tool_call_id: call.id,
                content: toolResultContent
            });
        }
    }
    return "I wasn't able to finish that within my step budget — please try rephrasing or ask about one case at a time.";
}

service / on new http:Listener(port) {

    resource function get health() returns HealthResponse {
        return {status: "ok", county: countyName};
    }

    resource function post chat(http:Request req, @http:Payload ChatRequest body) returns ChatResponse {
        string? oboToken = extractOboToken(req, body);
        if oboToken is () {
            log:printWarn("chat request received with no on-behalf-of token — the MCP server will deny it");
        }

        error? lastErr = ();
        foreach int attempt in 1 ..< (MAX_ATTEMPTS + 1) {
            string|error result = runChatLoop(body.message, oboToken);
            if result is string {
                return {response: result, session_id: body.session_id};
            }
            lastErr = result;
            if attempt < MAX_ATTEMPTS {
                log:printWarn(string `agent invocation failed (attempt ${attempt}/${MAX_ATTEMPTS}), retrying`, 'error = result);
                runtime:sleep(RETRY_BACKOFF_SECONDS * <decimal>attempt);
            }
        }
        log:printError(string `agent invocation failed after ${MAX_ATTEMPTS} attempts`, 'error = lastErr);
        return {response: TOOL_ACCESS_UNAVAILABLE_MESSAGE, session_id: body.session_id};
    }

    // Test-only escape hatch: lets a test script call ANY named MCP tool directly through
    // this agent's own connection/credentials, to prove the MCP server denies the 4
    // out-of-scope tools even when the call comes from the agent itself — not just when a
    // Python test client calls the server directly. The LLM tool loop above never has access
    // to this path; it only ever sees SCOPED_TOOLS. Deliberately not retry/degrade-wrapped —
    // a test script needs to see the raw error or scope-denial text, not a friendly fallback.
    resource function post debug/mcpCall(http:Request req, @http:Payload record {|string tool; map<json> arguments = {};|} body)
            returns record {|boolean isError; string text;|}|http:InternalServerError {
        string? oboToken = extractOboToken(req, {message: "", session_id: (), context: ()});
        mcp:CallToolResult|error result = callMcpTool(body.tool, body.arguments, oboToken);
        if result is error {
            return {isError: true, text: result.message()};
        }
        return {isError: result.isError == true, text: toolResultText(result)};
    }
}
