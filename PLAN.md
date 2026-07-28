# Agora — Agent Manager Demo Plan

> A pre-configured, pre-seeded demonstration of **WSO2 Agent Manager**, built around a
> fictional county government. The through-line: the **Agent Catalog as an instantiable
> workforce** — a small central team publishes agent *kinds*, and departments across the
> county each staff their own instances, under strict identity and governance controls.

**Org:** Riverside County — Department of Citizen Services (fictional)
**Sector:** Public sector
**State to seed:** ~6 months of production-like history

At a glance: **6 agent kinds · ~10 running instances · 5 departments · 3 environments · 5 user roles.**

---

## 1. The organization (backstory)

Riverside County consolidated its citizen-facing services under a single **Department of
Citizen Services**. A small central **AI Platform Team** (three people) builds and governs
agents; the people who actually *use* them are non-technical caseworkers, clerks, and
program officers spread across five departments.

Leadership set three non-negotiables — and these mandates are exactly what put the identity
and governance capabilities on stage:

- **No citizen PII leaves the county boundary** — sensitive workloads run on on-prem models.
- **Every agent action is audited** — a complete, reviewable trail for compliance.
- **Agents touch only what their role allows** — access is scoped by agent identity, not blanket credentials.

## 2. Departments & environments

**Departments** (drive both RBAC and the instantiation story):
Social Services · Permits & Licensing · Tax & Revenue · Records & Compliance · Contact Center
· **AI Platform Team** (central).

**Environments:**

| Environment | Purpose | Model policy |
|---|---|---|
| Development | Build & iterate on new instances | Cloud OK |
| Staging | Pre-production validation & evaluation | Cloud OK |
| Production | Live citizen-facing workloads | **On-prem for PII** |

Sensitive departments deploy the *same* agent to Production pinned to an on-prem model while
Development runs on cloud — a clean, env-aware governance contrast.

## 3. People & roles (RBAC — pre-created users)

| Persona | Department | Role | What they can do |
|---|---|---|---|
| Dana Okafor | AI Platform Team | **Admin** | Build & publish catalog kinds, set org LLM providers, MCP governance & guardrails |
| Marcus Lee | Social Services | **Developer** | Instantiate & configure agents for the department, deploy across environments |
| Priya Raman | Permits & Licensing | **Developer** | Same, scoped to Permits |
| Joan Ellis | Social Services | **Agent User** | Use instantiated agents only — no configuration access |
| Sam Whitfield | Records & Compliance | **Auditor** | Read-only across traces, audit log, and evaluations |

## 4. The catalog — the instantiable workforce (6 agent *kinds*)

| Agent kind | Purpose | Tools (via MCP) | LLM tier | Key guardrails |
|---|---|---|---|---|
| Citizen Inquiry Agent | Answer general questions, route requests | Knowledge base, service directory | Cloud | Tone; no promises |
| Benefits Eligibility Agent | Pre-screen benefit eligibility | Benefits Mgmt, Citizen Records | **On-prem** | No guaranteed-approval language; PII redaction |
| Permit & Licensing Agent | Guide & pre-fill permit applications | Permit DB, fee schedule | Cloud | No legal commitments |
| Case Management Agent | Summarize a case, draft next steps | Case system, Citizen Records | **On-prem** | Scoped to assigned cases only |
| Records / FOIA Agent | Intake & triage records requests | Records repo, redaction service | Cloud | Auto-redaction; exemption checks |
| Tax Assistance Agent | Answer tax-account questions | Tax system, Citizen Records | **On-prem** | No tax *advice*; account-scoped |

## 5. The money-shot: instantiation (few kinds → many instances)

- **Citizen Inquiry Agent → 4 instances**, one per department, each with its own knowledge
  base and branding. *Same workforce role, staffed everywhere.*
- **Benefits Eligibility Agent → 1 instance** in Social Services, deployed to Development and
  Production with a different model per environment.
- **Permit & Licensing Agent → 2 instances** (Building Permits and Business Licenses).
- **One external agent registered** — a legacy chatbot the county already runs — to show
  externally-hosted agent management alongside the native ones.

**Net effect:** ~6 kinds become ~10 running instances. The catalog visibly *scales a
workforce* rather than shipping one-off bots.

## 6. Tools & MCP governance

Backend systems exposed as MCP servers: **Citizen Records**, **Benefits Mgmt**, **Permit DB**,
**Tax System**, **Records Repository**, plus an external **State ID Verification** service.

Governance policies are pre-set by agent identity. The Permit agent's identity **cannot** reach
Citizen Records or the Tax system — so the demo can surface a **denied tool call in the audit
log** on cue. Identity-aware MCP governance: access is tied to *which agent* is calling, not a
shared service credential. A blocked call is the policy working, and it is recorded.

## 7. Identity & on-behalf-of

- **Auto-provisioned Agent ID** for every instance the moment it is created.
- **OAuth2 on-behalf-of** — when caseworker Joan runs the Case Management Agent, it accesses
  records *as Joan, scoped to her assigned cases* — never with god-mode access.
- **Third-party auth server integration** — the county's existing IDP fronts agent ingress.

**The visual that lands:** run the *same* agent as two different users and watch the data scope
change with them. Same instance, two identities, two views of the record store.

## 8. LLM providers & governance

| Provider | Used for | Bound to |
|---|---|---|
| Azure OpenAI (gov region) | Non-PII workloads | Inquiry, Permit, FOIA |
| On-prem Llama (vLLM) | PII workloads | Benefits, Case, Tax |

Providers are pre-registered at the org level with rate limits and guardrail policies.
Agent-level configuration binds the sensitive kinds to the on-prem model — the concrete proof
behind "citizen data never leaves our boundary."

## 9. Guardrails

Pre-applied and visible in the trace view the moment one fires:

- **PII redaction** on inputs and outputs.
- **No eligibility, legal, or tax promises** — blocks guaranteed-outcome language.
- **Professionalism & tone** appropriate to a government service.
- **Prompt-injection protection** at the LLM boundary.

## 10. Observability & evaluation (pre-populated)

Roughly six months of traces are seeded so no dashboard opens empty. Per-department volume,
latency, and cost trends are populated, alongside four evaluators running continuously:
**groundedness · PII-leak detection · tone · task accuracy**. Radar charts and time-series show
the on-prem Benefits agent scoring high on PII-safety, and the auditor view is fully populated
for a compliance walk-through.

## 11. Sandboxing

Eligibility calculations run inside a **hardened sandbox** with no access to host, network, or
filesystem — one clean scenario proving agent code cannot exfiltrate citizen data even if it
wanted to.

## 12. Suggested demo narrative

A single through-line that touches every headline capability in order:

1. **Admin publishes an agent kind** to the catalog. *(Catalog)*
2. A department **instantiates it in minutes** and deploys to an environment. *(Instantiation)*
3. Two different users run it and see **different data scopes**. *(Identity)*
4. A blocked tool call appears in the **audit log**. *(Governance)*
5. The **evaluation dashboard** proves quality and PII-safety over time. *(Observability)*
6. All of it running on **on-prem models** inside the county boundary. *(Data residency)*

---

## Open questions / decisions to make

- Exact agent runtime & framework for the built agents (LangChain / CrewAI / Ballerina / plain Python?).
- Real vs. mocked MCP backends — do we stand up lightweight fake services, or use recorded responses?
- How the on-prem model is represented in the demo environment (actual vLLM vs. a stand-in).
- Seed-data generation approach for the ~6 months of traces & evaluations.
- Deployment target for the demo (single k8s cluster vs. the multi-cluster story).
