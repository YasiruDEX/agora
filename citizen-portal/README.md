# Riverside County Citizen Portal

React + Vite + Tailwind front end for `riversidecounty.gov` (demo), per
[`PLAN.md`](../PLAN.md). A department-branded public portal with a floating/embedded chat
assistant per department, backed by the county's deployed agents in Agent Manager.

## Agents & mock fallback

Every chat surface goes through `src/services/agentApi.js`, keyed by an `agentKey` from
`src/mock/departmentData.js`'s `AGENTS` map. Each agent key independently falls back to a
scripted mock engine (`src/mock/agentMocks.js`) unless both of its env vars are set:

```env
VITE_AGENT_<KEY>_URL=<invoke URL from the agent's Overview page, no trailing /chat>
VITE_AGENT_<KEY>_API_KEY=<API Key from the same page>
```

`<KEY>` is the agentKey with dashes replaced by underscores, uppercased — e.g.
`benefits-eligibility` → `VITE_AGENT_BENEFITS_ELIGIBILITY_URL`.

Copy `.env.example` to `.env` and fill in real values as agents get deployed. A value left
blank, or starting with `REPLACE_WITH_`, is treated as unconfigured and uses the mock engine —
so the portal is always demoable even with only some agents wired up.

Currently wired to a real deployment: the Citizen Inquiry Agent (Social Services), which
backs both the `citizen-inquiry` key (the roaming floating assistant, rebranded per page) and
the `benefits-eligibility` key (the embedded assistant on `/social-services`) — both are the
same underlying deployed agent instance.

Real requests are sent as `POST <url>/chat` with header `X-API-Key: <apiKey>` and body
`{message, session_id, context}` — matching Agent Manager's own "Try It" tab. A caseworker
identity (for on-behalf-of-scoped agents like Case Management) is sent as `X-OBO-Token`.

## Setup

```bash
npm install
cp .env.example .env   # fill in real agent URLs/keys as needed
npm run dev
```

## Structure

- `src/pages/` — one page per department (Home, Contact Center, Social Services, Permits &
  Licensing, Tax & Revenue, Records & Compliance)
- `src/components/chat/ChatWidget.jsx` — the chat UI, used both floating (global) and embedded
  (department pages)
- `src/mock/departmentData.js` — department/agent metadata driving navigation and page content
- `src/mock/agentMocks.js` — scripted fallback responses for agents without a real backend yet
- `src/services/agentApi.js` — the mock/real dispatch described above
- `src/i18n/` — UI copy (English only currently; `LanguageContext` supports switching)
