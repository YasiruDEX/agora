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
import ballerina/http;
import ballerina/log;
import ballerina/os;

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
final string mcpApiKey = osGetEnv("MCP_API_KEY", "");
final string openAiApiKey = osGetEnv("OPENAI_API_KEY", "");
final string openAiModel = osGetEnv("OPENAI_MODEL", "gpt-4o-mini");

function osGetEnv(string name, string fallback) returns string {
    string val = os:getEnv(name);
    return val == "" ? fallback : val;
}

final chat:Client openAiClient = check new ({auth: {token: openAiApiKey}});

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

function mcpHeaders(string? oboToken) returns map<string|string[]> {
    map<string|string[]> headers = {"X-MCP-API-Key": mcpApiKey};
    if oboToken is string {
        headers["X-OBO-Token"] = oboToken;
    }
    return headers;
}

function callMcpTool(string name, map<json> arguments, string? oboToken) returns mcp:CallToolResult|error {
    // The Case Management MCP Server runs on Python/uvicorn (HTTP/1.1 only) — force HTTP/1.1
    // here, otherwise the default HTTP/2 client attempts an h2c upgrade uvicorn rejects
    // ("Unsupported upgrade request"), which surfaces as an intermittent transport error.
    mcp:StreamableHttpClient mcpClient = check new (mcpServerUrl, httpVersion = http:HTTP_1_1);
    check mcpClient->initialize({name: "case-management-agent", version: "0.1.0"}, {}, mcpHeaders(oboToken));
    mcp:CallToolResult result = check mcpClient->callTool({name, arguments}, mcpHeaders(oboToken));
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

            string toolResultContent;
            mcp:CallToolResult|error result = callMcpTool(toolName, argsMap, oboToken);
            if result is error {
                log:printError("MCP tool call failed", 'error = result, tool = toolName);
                toolResultContent = string `ERROR: ${result.message()}`;
            } else if result.isError == true {
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

    resource function post chat(http:Request req, @http:Payload ChatRequest body) returns ChatResponse|http:InternalServerError {
        string? oboToken = extractOboToken(req, body);
        if oboToken is () {
            log:printWarn("chat request received with no on-behalf-of token — the MCP server will deny it");
        }
        string|error result = runChatLoop(body.message, oboToken);
        if result is error {
            log:printError("chat turn failed", 'error = result);
            return <http:InternalServerError>{body: {response: string `Internal error: ${result.message()}`}};
        }
        return {response: result, session_id: body.session_id};
    }

    // Test-only escape hatch: lets a test script call ANY named MCP tool directly through
    // this agent's own connection/credentials, to prove the MCP server denies the 4
    // out-of-scope tools even when the call comes from the agent itself — not just when a
    // Python test client calls the server directly. The LLM tool loop above never has access
    // to this path; it only ever sees SCOPED_TOOLS.
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
