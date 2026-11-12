# One-command demo bootstrap

`bootstrap.py` stands up the whole Agora demo in an Agent Manager organization and serves
the citizen portal on your machine.

```bash
python deploy/bootstrap.py --dry-run
```

```bash
python deploy/bootstrap.py
```

| Step | What it does |
|---|---|
| 1 `preflight` | Checks credentials and warns if the branch Agent Manager builds is behind your checkout |
| 2 `project` | Creates the project if it does not exist |
| 3 `mcp-servers` | Deploys the knowledge base, permit database and state ID servers as platform-hosted components |
| 4 `mcp-proxies` | Puts an MCP proxy in front of each (one per department for the knowledge base) and deploys it |
| 5 `agents` | Creates, builds and deploys the four agents, connected to their proxies |
| 6 `api-keys` | Issues an API key per agent and reads back its invoke URL |
| 7 `evaluation` | Custom evaluators, monitors and alert thresholds |
| 8 `portal` | Writes the portal's `.env`, builds it and serves it at http://localhost:4173 |

What gets deployed is declared in [`stack.yaml`](stack.yaml). Organization, project and
environment come from [`evaluation/setup/targets.yaml`](../evaluation/setup/targets.yaml).

## Before the first real run

1. **Push first.** Agent Manager builds from GitHub (`repository.branch` in `stack.yaml`,
   default `main`), not from your checkout. Anything uncommitted or on another branch is not
   deployed. That includes the two new `openapi.yaml` files under `mcp-servers/`, which the
   MCP server components need.
2. Set `org`, `project`, `environment` and `llmProvider` in `targets.yaml`, and
   `project.deploymentPipeline` in `stack.yaml`, to names that exist in your organization.
3. Export credentials:

   ```bash
   export AMP_API_URL="https://<agent-manager-host>/api/v1"
   export AMP_TOKEN="<bearer token>"
   export OPENAI_API_KEY="<key the agents will use>"
   ```

A first run takes as long as seven builds: expect 20 to 40 minutes.

## Resuming and re-running

Every step checks what already exists, so re-running is safe. If a step stops, fix the cause
and continue from it:

```bash
python deploy/bootstrap.py --from agents
```

`--only <step>` runs a single step; `--no-serve` builds the portal without serving it.

Generated encryption keys, agent API keys and invoke URLs are kept in `deploy/.state/`
(git-ignored, readable only by you). Delete that folder only if you are also deleting the
deployed components: the MCP servers' data is encrypted with keys stored there.

After a run, load the agents' URLs and keys for traffic and score checks:

```bash
source deploy/.state/agent-keys.env
```

## Status: not yet run against a live organization

The script was written against Agent Manager's OpenAPI specification and verified in dry-run
mode only. Expect to adjust it on first contact. The places most likely to need a fix:

- **MCP servers as components.** Deploying an MCP server as a custom-API component and
  fronting it with a project MCP proxy (`source` = that component) follows the specification
  but is untested here.
- **Agent to proxy authentication.** Proxies are set to Agent ID security. The agents request
  tokens with the injected `AMP_AGENTID_*` variables; whether each agent's identity is
  granted access to its proxies automatically through `mcpConfig`, or needs a role, has not
  been confirmed.
- **Case Management.** It deploys the Ballerina agent with the embedded database. Its
  on-behalf-of token check needs the identity provider settings described in that agent's
  README, which this script does not configure.
- **Response field names** for builds, endpoints and environments are read as the
  specification describes them.

## The portal and API keys

The portal calls the agents from the browser, so each agent's API key is inside the built
JavaScript. Served from localhost that is private. Do not publish the `citizen-portal/dist`
folder to a public host.
