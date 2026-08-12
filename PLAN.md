# Agora — Agent Manager Demo Plan

> A pre-configured, pre-seeded demonstration of **WSO2 Agent Manager**, built around a
> fictional county government. The through-line: a **small catalog of agent kinds** built on
> **two different runtimes**, **strict role-based scopes**, and **MCP tool scoping** — one
> agent identity gets a wide, namespaced knowledge-base surface, another gets three named
> tools out of a much larger backend and a denied call to prove the boundary holds.

**Org:** Riverside County — Department of Citizen Services (fictional)
**Sector:** Public sector
**State to seed:** ~6 months of production-like history

At a glance: **3 agent kinds (2 runtimes) · ~9 running instances · 6 departments ·
3 environments · 3 deployment pipelines · 4 platform roles · 3 MCP servers (1 shared KB +
2 dedicated encrypted DBs) · 12 evaluators · 10 gateway guardrail/mediation policies.**

---

## 1. The organization (backstory)

Riverside County consolidated its citizen-facing services under a single **Department of
Citizen Services**. A small central **AI Platform Team** builds and governs agents; the
people who actually *use* them are non-technical caseworkers, clerks, and program officers
spread across five departments.

Leadership set three non-negotiables — and these mandates are exactly what put the identity
and governance capabilities on stage:

- **No citizen PII leaves the county boundary** — sensitive workloads run on a data-resident
  model tier, and every backend datastore is encrypted at rest.
- **Every agent action is audited** — a complete, reviewable trail for compliance.
- **Agents touch only what their role — and their MCP scope — allows** — access is scoped by
  agent identity down to individual tools, not blanket credentials.

## 2. Departments, environments & pipelines

**Departments** (drive both RBAC and the instantiation story):
Social Services · Permits & Licensing · Tax & Revenue · Records & Compliance · Contact Center
· **AI Platform Team** (central, non-citizen-facing).

**Environments:**

| Environment | Purpose | Model policy |
|---|---|---|
| Development | Build & iterate on new instances | Cloud OK |
| Staging | Pre-production validation & evaluator gating | Cloud OK |
| Production | Live citizen-facing workloads | **Data-resident tier for PII** |

**Deployment pipelines** — one per agent kind, each carrying its own promotion gate:

| Pipeline | Stages | Promotion gate into Production |
|---|---|---|
| Citizen Inquiry pipeline | Dev → Staging → Prod, fanned out per department instance | Tone evaluator passes threshold |
| Permit & Licensing pipeline | Dev → Staging → Prod | Step Success Rate evaluator passes threshold |
| Case Management pipeline | Dev → Staging → Prod | Tool Coverage + Content Safety pass + Admin sign-off |

Each pipeline is a real `amp:deployment-pipeline` resource. Developers can push to Dev/Staging
(`amp:agent:deploy-non-production`); only the Platform Admin holds
`amp:agent:deploy-production` and `amp:agent:promote` — so the Case Management pipeline visibly
stalls at the Staging gate until Dana approves it. That stall is the demo beat, not a bug.

## 3. Platform roles & scopes (RBAC)

Four roles, each a concrete set of `amp:*` scopes — not a vague "admin/user" label. This is
the primary way to show that Agent Manager access control is scope-granular, not a single
on/off toggle.

### Platform Admin — Dana Okafor, AI Platform Team

Publishes agent kinds, owns org-wide config, is the only identity that can push to
Production. Holds essentially the full scope catalog:

`amp:org:view`, `amp:org:modify-settings`, `amp:org:invite-member`, `amp:org:remove-member`,
`amp:org:assign-role`, `amp:org:manage-idp`, `amp:org:manage-service-account`,
`amp:role:create/read/update/delete`, `amp:group:create/read/update/delete`,
`amp:catalog:read`, `amp:project:create/read/update/delete`,
`amp:environment:create/read/update/delete`, `amp:gateway:create/read/update/delete`,
`amp:gateway:token-manage`, `amp:data-plane:read`,
`amp:deployment-pipeline:create/read/update/delete`, `amp:git-secret:create/read/delete`,
`amp:llm-provider-template:create/read/update/delete`,
`amp:llm-provider:create/read/update/delete`, `amp:llm-provider:configure-guardrail`,
`amp:llm-provider:connect`, `amp:llm-provider:deploy`, `amp:llm-provider:api-key-manage`,
`amp:mcp-server:create/read/update/delete`, `amp:mcp-server:configure-guardrail`,
`amp:mcp-server:connect`, `amp:mcp-server:api-key-manage`,
`amp:scope:create/read/update/delete`, `amp:agent-identity:create/read/update/delete`,
`amp:llm-proxy:create/read/update/delete`, `amp:llm-proxy:deploy`,
`amp:llm-proxy:api-key-manage`, `amp:evaluator:create/read/update/delete`,
`amp:agent:create/read/update/delete`, `amp:agent:build`, `amp:agent:promote`,
`amp:agent:rollback`, `amp:agent:suspend`, `amp:agent:deploy-non-production`,
`amp:agent:deploy-production`, `amp:agent:token-manage`, `amp:agent:api-key-manage`,
`amp:agent-kind:create/read/update/delete`, `amp:repository:read`,
`amp:monitor:create/read/update/delete/execute`, `amp:monitor:score-read`,
`amp:monitor:score-publish`, `amp:observability:trace-read/log-read/build-log-read/metric-read`,
`amp:profile:read`, `amp:profile:update-attributes`.

*Owns the git-secret entries that hold the MCP servers' database encryption keys — the only
role that can rotate them (§6).*

### Department Developer — Marcus Lee (Social Services), Priya Raman (Permits & Licensing)

Instantiates and configures agents for their own department, deploys freely to Dev/Staging,
**cannot** reach Production or delete platform-level resources:

`amp:agent:create`, `amp:agent:read`, `amp:agent:update`, `amp:agent:build`,
`amp:agent:deploy-non-production`, `amp:agent:token-manage`, `amp:agent-kind:read`,
`amp:catalog:read`, `amp:project:read`, `amp:environment:read`,
`amp:deployment-pipeline:read`, `amp:deployment-pipeline:update`, `amp:mcp-server:read`,
`amp:mcp-server:connect`, `amp:llm-provider:read`, `amp:llm-provider:connect`,
`amp:llm-proxy:read`, `amp:scope:read`, `amp:agent-identity:read`,
`amp:evaluator:create`, `amp:evaluator:read`, `amp:evaluator:update`,
`amp:monitor:create/read/update/execute`, `amp:monitor:score-read`,
`amp:observability:trace-read/log-read/metric-read`, `amp:repository:read`,
`amp:profile:read`, `amp:profile:update-attributes`.

Missing on purpose: `amp:agent:deploy-production`, `amp:agent:promote/rollback/suspend`,
`amp:agent:delete`, `amp:mcp-server:create/update/delete`, `amp:llm-provider:create/update`,
`amp:org:*`, `amp:role:*`, `amp:group:*`, `amp:git-secret:*`, `amp:gateway:*`. A Developer can
*use* an MCP server's API key that was issued to their instance, but cannot mint or rotate one.

### Agent Operator — Joan Ellis, Social Services (day-to-day agent user)

Runs the agents that are already deployed to her department. No build, no config, no
visibility into other departments' traces:

`amp:agent:read`, `amp:catalog:read`, `amp:project:read`, `amp:environment:read`,
`amp:monitor:read`, `amp:observability:log-read`, `amp:profile:read`,
`amp:profile:update-attributes`.

Everything else — create/update/delete on any resource, evaluator access, MCP/LLM
configuration, deployment pipelines — is absent. This is the role that makes on-behalf-of
access meaningful: Joan's *own* identity carries no elevated data access, so the Case
Management Agent's downstream reach is bounded by *her* permissions, not the agent's.

### Auditor — Sam Whitfield, Records & Compliance

Read-only across the entire platform, including score visibility, for compliance review —
never a mutating scope:

`amp:org:view`, `amp:catalog:read`, `amp:project:read`, `amp:environment:read`,
`amp:gateway:read`, `amp:data-plane:read`, `amp:deployment-pipeline:read`,
`amp:git-secret:read`, `amp:llm-provider-template:read`, `amp:llm-provider:read`,
`amp:mcp-server:read`, `amp:scope:read`, `amp:agent-identity:read`, `amp:llm-proxy:read`,
`amp:evaluator:read`, `amp:agent:read`, `amp:agent-kind:read`, `amp:repository:read`,
`amp:profile:read`, `amp:monitor:read`, `amp:monitor:score-read`,
`amp:observability:trace-read/log-read/build-log-read/metric-read`.

No `score-publish`, no `configure-guardrail`, no create/update/delete anywhere — the auditor
can see every score and every trace and change nothing. `amp:git-secret:read` lets Sam confirm
an encryption key *exists and was rotated on schedule* without ever reading its value.

## 4. Technology stack

Two agent runtimes on purpose — the point being that Agent Manager's governance layer (roles,
scopes, guardrails, evaluators, pipelines) applies identically regardless of what the agent is
written in.

| Component | Stack | Notes |
|---|---|---|
| Citizen Inquiry Agent | Python 3.11 + LangChain (`langchain-mcp-adapters` for tool binding) | One image, 5 instances differing only by injected env vars |
| Permit & Licensing Agent | Python 3.11 + LangChain | Same stack as Citizen Inquiry; 2 instances from one image, different prompt-template config |
| Case Management Agent | **Ballerina** (native MCP client) | Deliberately different runtime — proves governance is language-agnostic |
| Unified KB MCP Server | Python + `mcp`/FastMCP SDK | Embedded local vector store, namespace-partitioned per department (§6) |
| Permit DB MCP Server | Python + FastMCP SDK | Embedded local SQLite, SQLCipher-encrypted (§6) |
| Case Management MCP Server | Python + FastMCP SDK | Embedded local SQLite, SQLCipher-encrypted, 7 tools / 3 scoped in (§6, §7) |
| LLM Proxy | Agent Manager LLM Proxy | Fronts Azure OpenAI + AWS Bedrock GovCloud (§9) |
| Packaging | Containers (one image per agent kind, one per MCP server) | Built via `amp:agent:build`; promoted through the pipelines in §2 |
| Orchestration | Agent Manager control plane + shared cluster | MCP servers are platform infra the Admin manages (`amp:mcp-server:*`), not redeployed per instance |

MCP is transport-level and language-agnostic, so all three MCP servers are implemented in
Python regardless of which agent talks to them — the Ballerina Case Management Agent calls the
Python-hosted Case Management MCP server over the same MCP protocol a Python agent would use.

## 5. The catalog — 3 agent kinds

Down to three kinds on purpose: fewer kinds, sharper contrast between "broadly instantiated
utility agent" and "narrowly scoped, sensitive-data agent."

| Agent kind | Runtime | Purpose | MCP server | LLM tier |
|---|---|---|---|---|
| Citizen Inquiry Agent | Python/LangChain | Answer general questions, route requests | Unified KB MCP — full read/write tool set, namespace-scoped | Cloud |
| Permit & Licensing Agent | Python/LangChain | Guide & pre-fill permit applications | Dedicated Permit DB MCP + external State ID Verification MCP | Cloud |
| Case Management Agent | Ballerina | Summarize a case, draft next steps | Dedicated Case Management MCP — **3 of 7 tools** scoped in | Data-resident (AWS Bedrock GovCloud) |

Case Management Agent lives in **Social Services only** — it is not fanned out, because the
whole point of keeping it singular is to make the MCP scoping story legible: one agent kind,
one department, one MCP server with a visibly restricted tool surface.

## 6. Instantiation & MCP architecture

### Instances

- **Citizen Inquiry Agent → 5 instances**, one per citizen-facing department (Social
  Services, Permits & Licensing, Tax & Revenue, Records & Compliance, Contact Center). Every
  instance is the *same* image and prompt, pointed at the *same* Unified KB MCP server, but
  each carries a **different `MCP_API_KEY`** — the server maps that key to one department
  namespace, so `dept=social-services` literally cannot read the `dept=tax-revenue` partition
  even though the tool call looks identical.
- **Permit & Licensing Agent → 2 instances** (Building Permits and Business Licenses), both
  in Permits & Licensing, both pointed at the same dedicated Permit DB MCP server, each with
  its own permit-type prompt template.
- **Case Management Agent → 1 instance**, Social Services, deployed to Development on a cloud
  model and to Production pinned to the data-resident AWS GovCloud Bedrock tier.
- **One external agent registered** — the county's legacy contact-center chatbot — attached
  to the gateway with a `redirect` policy that forwards its old endpoint to the new Contact
  Center Citizen Inquiry instance.

**Net effect:** 3 kinds become ~9 running instances (5 + 2 + 1 + 1 external).

### MCP servers: one shared KB, two dedicated encrypted DBs

Permit & Licensing and Case Management each get **their own dedicated MCP server for database
management** — separate processes, separate encrypted stores, never shared with each other or
with the KB server. The Citizen Inquiry Agent's knowledge, by contrast, is deliberately
**shared** across departments behind one server, partitioned by namespace.

| MCP server | Serves | Data store | Encryption |
|---|---|---|---|
| Unified KB MCP Server | Citizen Inquiry (all 5 instances) | Embedded local vector/document store, one namespace per department (`social-services`, `permits-licensing`, `tax-revenue`, `records-compliance`, `contact-center`) | Encrypted at rest |
| Permit DB MCP Server | Permit & Licensing (both instances) | Embedded local SQLite — permit applications, fee schedules | **SQLCipher (AES-256)** |
| Case Management MCP Server | Case Management (1 instance) | Embedded local SQLite — case records, citizen profiles | **SQLCipher (AES-256)** |

All three run **locally inside the MCP server process itself** — no external managed database.
This is a deliberate simplification and a data-residency talking point: the sensitive data
never leaves the MCP server's own encrypted volume, and that volume's encryption key is a
`amp:git-secret` entry only the Platform Admin can create or rotate (§3).

**Unified KB namespacing.** The KB server exposes four tools shared by every Citizen Inquiry
instance:

| Tool | Effect |
|---|---|
| `kb_search(query)` | Semantic search over the caller's namespace |
| `kb_read(doc_id)` | Fetch a specific knowledge-base article from the caller's namespace |
| `kb_write(doc_id, content)` | Create or update an article in the caller's namespace |
| `kb_list_sources()` | List source documents the caller's namespace was built from |

Same server, same four tools, five namespaces — isolation enforced entirely by which API key
resolved to which namespace, not by deploying five copies of the server. `mcp-ratelimit` is
applied per tool (`kb_search`, `kb_write` each get their own limit/duration entry) so one
namespace's traffic can't starve another's.

### Connecting an agent to its MCP server

Every agent instance authenticates to its MCP server with an **API key over the MCP server's
URL** — no shared service credential, no implicit trust. At deploy time, Agent Manager injects
two environment variables into the instance:

- `MCP_SERVER_URL` — the target MCP endpoint (identical for all 5 KB instances; distinct per
  dedicated DB server).
- `MCP_API_KEY` — an instance-specific key, minted and managed under `amp:mcp-server:api-key-manage`.
  For Citizen Inquiry this key is what resolves to a department namespace server-side; for
  Permit & Licensing and Case Management it is the sole credential the dedicated server
  accepts at all.

This is literally what "a different environment credential per department" means in practice
— it is this env-injected API key, nothing more exotic.

## 7. MCP tool scoping — the Case Management Agent is the demo

The dedicated Case Management MCP server exposes **seven** tools against the county case
system:

`case_search`, `case_read`, `case_notes_write`, `case_status_update`, `citizen_profile_read`,
`citizen_profile_write`, `case_close`.

The Case Management Agent's identity is granted a **scope containing exactly three**:
`case_search`, `case_read`, `case_notes_write`. Everything else — `citizen_profile_write`,
`case_close`, and critically `citizen_profile_read` beyond the assigned case — is outside the
agent's scope.

This is the deliberate demo beat: **live in a trace where the model attempts
`citizen_profile_read` on a citizen outside the caseworker's assignment, the call is denied by
MCP scope enforcement before it reaches the encrypted store, and the denial is written to the
audit log** — not a crash, not a hallucinated success, a clean policy rejection. `amp:scope:read`
(everyone) vs. `amp:scope:create/update` (Admin only) is what makes that scope Dana's-to-change-
not-Marcus's-to-change, tying §3's RBAC directly to this MCP boundary.

## 8. Identity & on-behalf-of

- **Auto-provisioned Agent ID** for every instance the moment it is created.
- **OAuth2 on-behalf-of** — when caseworker Joan runs the Case Management Agent, it accesses
  records *as Joan, scoped to her assigned cases* — never with god-mode access. Combined with
  §3, Joan's own `amp:*` scopes (Agent Operator — no case-system access of her own) plus the
  agent's MCP scope (§7) form two independent boundaries the demo can show stacking.
- **Third-party auth server integration** — the county's existing IDP fronts agent ingress;
  the Case Management MCP server validates the on-behalf-of token via **Opaque Token Auth**
  (RFC 7662 introspection) before it will honor any of the three scoped tools, on top of the
  API-key check in §6.

**The visual that lands:** run the *same* Case Management Agent as two different caseworkers
and watch `case_search` return two different case lists — same instance, same MCP scope, two
identities, two data views.

## 9. LLM proxy & guardrails

An **Agent Manager LLM Proxy** sits in front of every provider — agents never call a model
endpoint directly.

| Provider | Bound to | Data residency |
|---|---|---|
| Azure OpenAI (gov region) | Citizen Inquiry, Permit & Licensing | Cloud |
| AWS Bedrock (GovCloud) via OpenAI→Bedrock Transformer, SigV4-signed | Case Management | Data-resident |

Kept deliberately small — **3–4 guardrails per agent kind**, chosen for what actually matters
for that kind's risk profile, not the full policy catalog:

| Agent kind | Guardrails |
|---|---|
| Citizen Inquiry Agent | PII Masking Regex, Content Length Guardrail, Prompt Decorator (department branding) |
| Permit & Licensing Agent | JSON Schema Guardrail (validates structured application data), Word Count Guardrail, URL Guardrail (fee-schedule links) |
| Case Management Agent | PII Masking Regex, Opaque Token Auth (on-behalf-of introspection), mcp-ratelimit |

Plus two platform-level policies that aren't tied to a single agent kind:

- **AWS Authentication** (SigV4/STS) — signs the Case Management LLM proxy's outbound calls to
  Bedrock GovCloud.
- **`redirect`** — migrates the external legacy chatbot's traffic to the new Contact Center
  Citizen Inquiry instance at the gateway.

## 10. Evaluators — 12 selected, mapped by agent kind

Running all 24 available evaluators on every trace is unnecessary for this demo; **4 per agent
kind** is enough to prove the observability story without drowning the dashboard:

| Agent kind | Evaluators |
|---|---|
| Citizen Inquiry Agent | Latency Performance (rule), Length Compliance (rule), Helpfulness (judge), Tone (judge) |
| Permit & Licensing Agent | Step Success Rate (rule), Sequence Adherence (rule), Instruction Following (judge), Completeness (judge) |
| Case Management Agent | Tool Coverage (rule), Content Safety (rule), Groundedness (judge), Safety (judge) |

Two of these are load-bearing for the rest of the plan, not just filler:

- **Tool Coverage** on Case Management directly measures whether the agent stayed inside its
  three-tool MCP scope (§7) — a scoping violation shows up as a failing evaluator score, not
  just an audit-log line.
- **Content Safety** on Case Management is the automated backstop behind the PII Masking
  Regex guardrail (§9) — belt-and-suspenders on the same risk.

Rule-based evaluators are free and run on every trace; the judge evaluators run on a sample
using the org's own LLM proxy. Score visibility follows §3: `amp:monitor:score-read` for
Admin/Developer/Auditor, `amp:monitor:score-publish` for Admin only (that's the gate the
Case Management pipeline in §2 depends on).

## 11. Sandboxing

Any code execution the Permit & Licensing Agent needs (fee calculations, form validation)
runs inside a **hardened sandbox** with no access to host, network, or filesystem — one clean
scenario proving agent-generated code cannot exfiltrate citizen data even if it wanted to.

## 12. Development plan

Sequenced so every phase produces something demoable, rather than a big-bang integration at
the end.

**Phase 0 — Platform foundations** *(Platform team)*
- Stand up the Agent Manager org, 3 environments, 4 roles + their `amp:*` scopes, invite the
  5 personas.
- Create the `amp:git-secret` entries that will hold the two SQLCipher encryption keys.

**Phase 1 — MCP servers**
- Build the Unified KB MCP Server (Python/FastMCP): namespace-partitioned local store, seed
  starter documents per department, implement `kb_search`/`kb_read`/`kb_write`/`kb_list_sources`.
- Build the Permit DB MCP Server (Python/FastMCP): SQLCipher-encrypted local SQLite, seed
  permit/fee data, implement `permit_lookup`/`fee_schedule_read`/`application_prefill`.
- Build the Case Management MCP Server (Python/FastMCP): SQLCipher-encrypted local SQLite,
  seed case records, implement all 7 tools.
- Register all three with Agent Manager (`amp:mcp-server:create`); mint per-consumer API keys.

**Phase 2 — Agent kinds**
- Build the Citizen Inquiry Agent kind (Python/LangChain), wire `MCP_SERVER_URL`/`MCP_API_KEY`
  env injection, publish to the catalog.
- Build the Permit & Licensing Agent kind (Python/LangChain) against the dedicated Permit DB
  MCP + external State ID Verification MCP.
- Build the Case Management Agent kind (Ballerina) against the dedicated Case Management MCP,
  wire the 3-tool scope (§7) and the OAuth2 on-behalf-of flow (§8).

**Phase 3 — Instantiation & pipelines**
- Instantiate Citizen Inquiry × 5 departments with distinct namespace-mapped API keys, Permit
  & Licensing × 2, Case Management × 1.
- Register the external legacy chatbot and its gateway `redirect` policy.
- Stand up the 3 deployment pipelines and their promotion gates (§2).

**Phase 4 — LLM proxy & guardrails**
- Register Azure OpenAI and AWS Bedrock GovCloud behind the LLM Proxy; wire the
  OpenAI→Bedrock Transformer and AWS Authentication for the Bedrock leg.
- Attach the 3–4 guardrails per agent kind from §9.

**Phase 5 — Evaluators & seed data**
- Configure the 12 evaluators from §10.
- Generate ~6 months of synthetic traces per instance and backfill evaluator scores,
  including at least one deliberate MCP-scope-denial trace for Case Management.

**Phase 6 — Rehearsal**
- Walk the demo narrative (§13) end-to-end as each persona; confirm the RBAC denial, the
  MCP-scope denial, and the identity-swap moment all fire on cue.

## 13. Suggested demo narrative

A single through-line that touches every headline capability in order:

1. **Admin (Dana) publishes the 3 agent kinds** to the catalog with their scopes and
   guardrails pre-attached. *(Catalog · RBAC)*
2. **Developer (Marcus/Priya) instantiates Citizen Inquiry** into their department — same
   image, new `MCP_API_KEY`, new namespace, deployed to Dev then Staging. *(Instantiation ·
   Technology stack)*
3. Show the **same tool, five departments, five API keys** — the unified KB server never
   changes; only the identity does. *(Unified MCP server)*
4. **Case Management Agent** (Ballerina) attempts a tool outside its granted scope; the call
   is **denied and logged**. *(MCP tool scoping — the centerpiece)*
5. **Two caseworkers run the same Case Management instance**; on-behalf-of access returns two
   different case lists. *(Identity)*
6. **Evaluators score the last six months of traces live** — Tool Coverage flags the denied
   call, Content Safety confirms no PII leaked despite the attempt. *(Observability)*
7. **Promote Permit & Licensing from Staging to Production** as Marcus — denied, no
   `amp:agent:deploy-production`. Dana promotes it instead. *(RBAC enforcing the pipeline gate)*
8. **Flip to the Auditor (Sam)** — full read access to every trace, score, and scope, zero
   ability to change anything. *(Read-only compliance role)*
9. **Legacy chatbot traffic redirects** to the new Contact Center instance live at the
   gateway. *(External agent migration)*
10. All PII-bearing traffic for Case Management is confirmed running through the AWS GovCloud
    Bedrock tier, SigV4-signed, against SQLCipher-encrypted local stores. *(Data residency)*

---

## Open questions / decisions to make

- Which Ballerina MCP client library/module to standardize on for the Case Management Agent.
- Exact local vector-store choice for the Unified KB MCP Server (embedded Chroma vs.
  SQLite+FTS) — affects seed-data generation.
- Whether SQLCipher key rotation is simulated once during the demo or left static.
- Seed-data generation approach for the ~6 months of traces & the 12-evaluator score history.
- Deployment target for the demo (single k8s cluster vs. the multi-cluster story).
- Whether the external legacy chatbot is a real stubbed service or a static redirect target.
