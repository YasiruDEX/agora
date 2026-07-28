# Agora

> **Agora** — the civic gathering place and marketplace. A pre-configured, pre-seeded
> demonstration of **WSO2 Agent Manager** where a fictional county government's departments
> browse a catalog of pre-built agents and staff their own **instantiable workforce**.

This repo is where we iteratively design and build the demo scenario. It starts as a plan and
grows into the actual configuration, seed data, and supporting services as we implement it.

## The story in one line

A small central AI Platform Team publishes agent *kinds* to the catalog; departments across
**Riverside County — Department of Citizen Services** instantiate their own, under strict
identity and governance controls (on-behalf-of access, identity-aware MCP governance, on-prem
models for PII, full auditing).

## Repo layout

```
agora/
├── README.md                    # you are here
├── PLAN.md                      # the full demo blueprint — the working source of truth
└── docs/
    └── demo-blueprint.html      # visual (civic-report) version of the plan
```

## Status

🌱 **Planning.** The scenario is defined in [`PLAN.md`](./PLAN.md). Nothing is built yet.

## Roadmap (rough)

- [x] Define the demo scenario & story (see `PLAN.md`)
- [ ] Resolve the open questions at the bottom of `PLAN.md` (runtime, mocked vs. real backends, seed-data approach)
- [ ] Model the org: departments, users, roles, environments
- [ ] Build the catalog agent kinds
- [ ] Wire up MCP backends + governance policies
- [ ] Configure identity flows (Agent IDs, OAuth2 on-behalf-of, IDP)
- [ ] Register LLM providers + guardrails
- [ ] Instantiate the workforce (~10 instances)
- [ ] Generate ~6 months of seed traces & evaluations
- [ ] Rehearse the demo narrative end-to-end

## How we work in here

`PLAN.md` is the source of truth for the *what*. As we implement, we add the *how* alongside it
and keep the plan in sync. Commit iteratively.
