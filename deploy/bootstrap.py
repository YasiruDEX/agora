"""Stand up the whole Agora demo with one command.

    python deploy/bootstrap.py --dry-run     # print every step and request, change nothing
    python deploy/bootstrap.py               # run all steps
    python deploy/bootstrap.py --from agents # resume from a step
    python deploy/bootstrap.py --only portal # run one step

Steps, in order:
    preflight    credentials, and that the branch to build is pushed
    project      create the project if it does not exist
    mcp-servers  deploy the three MCP servers as platform-hosted components
    mcp-proxies  put an MCP proxy in front of each and deploy it to the environment
    agents       create, build and deploy the four agents, connected to their proxies
    api-keys     issue an API key per agent and read back its invoke URL
    evaluation   custom evaluators, monitors and alert thresholds (evaluation/setup/apply.py)
    portal       write the citizen portal's .env, build it, and serve it on localhost

Safe to re-run: every step looks for what already exists first. Generated secrets, API keys
and invoke URLs are kept in deploy/.state/ (git-ignored).

Environment:
    AMP_API_URL, and AMP_TOKEN or AMP_TOKEN_URL + AMP_CLIENT_ID + AMP_CLIENT_SECRET
    OPENAI_API_KEY          given to the agents as a sensitive value
    AMP_ALERT_WEBHOOK_URL   optional, for threshold alerts
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import string
import subprocess
import sys
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "evaluation" / "setup"))
import apply as evaluation  # noqa: E402  (evaluation/setup/apply.py)

STACK = yaml.safe_load((REPO / "deploy" / "stack.yaml").read_text())
STATE_DIR = REPO / "deploy" / ".state"
STATE_FILE = STATE_DIR / "state.json"
STEPS = ["preflight", "project", "mcp-servers", "mcp-proxies", "agents", "api-keys", "evaluation", "portal"]
BUILD_TIMEOUT_S, DEPLOY_TIMEOUT_S, POLL_S = 30 * 60, 10 * 60, 15


class Run:
    """Shared context for the steps: API client, targets, persisted state."""

    def __init__(self, dry_run: bool) -> None:
        self.dry_run = dry_run
        self.api = evaluation.Api(dry_run=dry_run)
        self.targets = evaluation.load_targets()
        self.org, self.project, self.env = (self.targets[k] for k in ("org", "project", "environment"))
        self.state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
        for bucket in ("secrets", "images", "proxyUrls", "invokeUrls", "apiKeys"):
            self.state.setdefault(bucket, {})

    def save(self) -> None:
        if self.dry_run:
            return
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(self.state, indent=2))
        STATE_FILE.chmod(0o600)

    @property
    def project_path(self) -> str:
        return f"/orgs/{evaluation._seg(self.org)}/projects/{evaluation._seg(self.project)}"

    def agent_path(self, name: str) -> str:
        return f"{self.project_path}/agents/{evaluation._seg(name)}"

    def secret(self, name: str) -> str:
        """A generated secret, created on first use and reused afterwards."""
        if name not in self.state["secrets"]:
            kind = STACK["secrets"][name]
            if kind == "fernet":
                value = base64.urlsafe_b64encode(os.urandom(32)).decode()
            else:
                value = secrets.token_urlsafe(32)
            if self.dry_run:
                return f"<generated {kind}: {name}>"
            self.state["secrets"][name] = value
            self.save()
        return self.state["secrets"][name]

    def env_list(self, spec: dict) -> list[dict]:
        """Turn a stack.yaml env block into Agent Manager environment variables."""
        out = []
        for key, value in (spec or {}).items():
            sensitive = False
            if isinstance(value, dict) and "secret" in value:
                value, sensitive = self.secret(value["secret"]), True
            elif isinstance(value, dict) and "env" in value:
                name = value["env"]
                value, sensitive = os.environ.get(name, ""), True
                if not value:
                    if not self.dry_run:
                        sys.exit(f"{name} is not set in your shell; {key} needs it")
                    value = f"<value of ${name}>"
            elif isinstance(value, dict) and "json" in value:
                names = {n: self.secret(n) for n in STACK["secrets"]}
                value = json.dumps({string.Template(k).substitute(names): v for k, v in value["json"].items()})
                sensitive = True
            out.append({"key": key, "value": str(value), "isSensitive": sensitive})
        return out


def say(text: str) -> None:
    print(f"\n=== {text} ===", flush=True)


def wait_for(what: str, probe, timeout_s: int, run: Run):
    """Poll `probe` until it returns a value. In a dry run, return a placeholder at once."""
    if run.dry_run:
        print(f"  (would wait for {what})")
        return f"<{what}>"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        value = probe()
        if value:
            return value
        print(f"  waiting for {what} ...", flush=True)
        time.sleep(POLL_S)
    sys.exit(f"Timed out after {timeout_s // 60} min waiting for {what}. Re-run with --from <step> once it is ready.")


def step_preflight(run: Run) -> None:
    repo = STACK["repository"]
    print(f"  organization {run.org}, project {run.project}, environment {run.env}")
    print(f"  builds from {repo['url']} @ {repo['branch']}")
    git = lambda *args: subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True).stdout.strip()  # noqa: E731
    subprocess.run(["git", "-C", str(REPO), "fetch", "--quiet", "origin", repo["branch"]], check=False)
    remote, local = git("rev-parse", f"origin/{repo['branch']}"), git("rev-parse", "HEAD")
    dirty = git("status", "--porcelain")
    if remote != local or dirty:
        print(f"  WARNING: Agent Manager builds origin/{repo['branch']} ({remote[:8] or 'not found'}).")
        print(f"           Your checkout is at {local[:8]}" + (" with uncommitted changes" if dirty else "") + ".")
        print("           Anything not pushed to that branch will not be in the deployed agents.")
    if not run.dry_run:
        if run.api.read(f"/orgs/{evaluation._seg(run.org)}/environments") is None:
            sys.exit(f"Organization '{run.org}' was not found, or these credentials cannot read it.")
        if not os.environ.get("OPENAI_API_KEY"):
            sys.exit("OPENAI_API_KEY is not set; the agents need it.")


def step_project(run: Run) -> None:
    if run.api.read(run.project_path) is not None:
        print(f"  project {run.project} exists")
        return
    spec = STACK["project"]
    run.api.write(
        "POST",
        f"/orgs/{evaluation._seg(run.org)}/projects",
        {
            "name": run.project,
            "displayName": spec["displayName"],
            "description": spec.get("description", ""),
            "deploymentPipeline": spec["deploymentPipeline"],
        },
    )


def component_body(run: Run, spec: dict, sub_type: str, mcp_config: list | None = None) -> dict:
    repo = STACK["repository"]
    buildpack = {"language": spec.get("language", "python")}
    if spec.get("languageVersion") or buildpack["language"] == "python":
        buildpack["languageVersion"] = spec.get("languageVersion", "3.11")
    if spec.get("runCommand"):
        buildpack["runCommand"] = spec["runCommand"]
    interface = {"type": "HTTP", "port": spec["port"], "basePath": "/"}
    if sub_type == "custom-api":
        interface["schema"] = {"path": "/openapi.yaml"}
    body = {
        "name": spec["name"],
        "displayName": spec["displayName"],
        "description": spec.get("description", ""),
        "provisioning": {
            "type": "internal",
            "repository": {"url": repo["url"], "branch": repo["branch"], "appPath": spec["appPath"], "secretRef": None},
        },
        "agentType": {"type": "agent-api", "subType": sub_type},
        "build": {"type": "buildpack", "buildpack": buildpack},
        "inputInterface": interface,
        "configurations": {"env": run.env_list(spec.get("env"))},
    }
    if mcp_config:
        body["mcpConfig"] = mcp_config
    return body


def build_and_deploy(run: Run, spec: dict, body: dict, api_key_security: bool) -> None:
    """Create the component if missing, wait for a successful build, deploy it."""
    name, path = spec["name"], run.agent_path(spec["name"])
    print(f"\n-- {name}")
    if run.api.read(path) is None:
        run.api.write("POST", f"{run.project_path}/agents", body)
    else:
        print("  exists")

    def latest_build():
        builds = (run.api.read(f"{path}/builds", {"limit": 5}) or {}).get("builds") or []
        return builds[0] if builds else None

    if not run.dry_run and latest_build() is None:
        run.api.write("POST", f"{path}/builds")
    elif run.dry_run:
        print(f"\nPOST {path}/builds   (only if creating the component did not start one)")

    def built_image():
        build = latest_build()
        if build and build.get("status") == "Failed":
            sys.exit(f"Build of {name} failed. Open its Build page in Agent Manager for the log, fix, push, re-run.")
        if build and build.get("status") in ("Succeeded", "Completed") and build.get("imageId"):
            return build["imageId"]
        return None

    image = wait_for(f"build of {name}", built_image, BUILD_TIMEOUT_S, run)
    if run.state["images"].get(name) == image and run.api.read(f"{path}/endpoints", {"environment": run.env}):
        print("  already deployed from this build")
        return
    deploy = {
        "imageId": image,
        "env": run.env_list(spec.get("env")),
        "enableAutoInstrumentation": True,
        "enableApiKeySecurity": api_key_security,
    }
    if api_key_security:  # the portal runs on another origin and sends X-API-Key
        deploy["corsConfig"] = {
            "enabled": True,
            "allowOrigin": [f"http://localhost:{STACK['portal']['port']}", "http://localhost:5173"],
            "allowMethods": ["POST", "GET", "OPTIONS"],
            "allowHeaders": ["Content-Type", "Accept", "X-API-Key", "X-OBO-Token"],
        }
    run.api.write("POST", f"{path}/deployments", deploy)
    wait_for(f"{name} to be reachable in {run.env}", lambda: endpoint_of(run, name), DEPLOY_TIMEOUT_S, run)
    run.state["images"][name] = image
    run.save()


def endpoint_of(run: Run, name: str) -> dict | None:
    """The component's first endpoint in the environment: {name, url}."""
    endpoints = run.api.read(f"{run.agent_path(name)}/endpoints", {"environment": run.env}) or {}
    for key, value in endpoints.items():
        if isinstance(value, dict) and value.get("url"):
            return {"name": value.get("endpointName", key), "url": value["url"]}
    return None


def step_mcp_servers(run: Run) -> None:
    for spec in STACK["mcpServers"]:
        # No gateway API key here: the MCP proxy is the only caller, over the in-cluster address.
        build_and_deploy(run, spec, component_body(run, spec, "custom-api"), api_key_security=False)


def step_mcp_proxies(run: Run) -> None:
    for proxy in STACK["mcpProxies"]:
        print(f"\n-- {proxy['id']}")
        endpoint = endpoint_of(run, proxy["server"]) if not run.dry_run else {"name": f"<endpoint of {proxy['server']}>"}
        if endpoint is None:
            sys.exit(f"{proxy['server']} has no endpoint in {run.env} yet. Run --from mcp-servers first.")
        path = f"{run.project_path}/mcp-proxies/{evaluation._seg(proxy['id'])}"
        run.api.write(
            "PUT",
            path,
            {"name": proxy["name"], "source": {"componentName": proxy["server"], "endpointName": endpoint["name"]}},
        )
        binding = run.api.write(
            "PUT",
            f"{path}/environments/{evaluation._seg(run.env)}",
            {
                "security": {"enabled": True, "identity": {"enabled": True}},
                "upstreamAuth": {
                    "type": "api-key",
                    "header": STACK["upstreamKeyHeader"],
                    "value": run.secret(proxy["upstreamKey"]),
                },
            },
        )
        if binding.get("publicUrl"):
            run.state["proxyUrls"][proxy["id"]] = binding["publicUrl"]
            run.save()


def step_agents(run: Run) -> None:
    for spec in STACK["agents"]:
        mcp_config = [
            {"proxyName": proxy_id, "environmentVariables": [{"key": "url", "name": env_name}]}
            for proxy_id, env_name in (spec.get("mcp") or {}).items()
        ]
        build_and_deploy(run, spec, component_body(run, spec, "chat-api", mcp_config), api_key_security=True)


def step_api_keys(run: Run) -> None:
    listed = run.api.read(f"/orgs/{evaluation._seg(run.org)}/environments") or []
    # The API returns a bare list; older builds wrapped it as {"environments": [...]}.
    environments = listed.get("environments") or [] if isinstance(listed, dict) else listed
    env_id = next((e.get("id") or e.get("uuid") for e in environments if e.get("name") == run.env), None)
    if env_id is None:
        if not run.dry_run:
            sys.exit(f"Environment '{run.env}' was not found in organization '{run.org}'.")
        env_id = f"<id of {run.env}>"
    for spec in STACK["agents"]:
        name = spec["name"]
        endpoint = endpoint_of(run, name) if not run.dry_run else {"url": f"<invoke URL of {name}>"}
        if endpoint is None:
            sys.exit(f"{name} has no endpoint in {run.env} yet. Run --from agents first.")
        run.state["invokeUrls"][name] = endpoint["url"].rstrip("/")
        if name in run.state["apiKeys"]:
            print(f"  {name}: reusing the stored API key")
            continue
        created = run.api.write(
            "POST",
            f"{run.agent_path(name)}/environments/{evaluation._seg(env_id)}/api-keys",
            {"displayName": "Agora demo portal and traffic"},
        )
        if created.get("apiKey"):
            run.state["apiKeys"][name] = created["apiKey"]
        run.save()
    write_local_targets(run)


def write_local_targets(run: Run) -> Path:
    """A copy of targets.yaml with the real invoke URLs, for traffic/run.py and apply.py."""
    targets = json.loads(json.dumps(run.targets))
    exports = []
    for agent in targets["agents"]:
        url = run.state["invokeUrls"].get(agent["name"])
        if url:
            agent["invokeUrl"] = url + "/chat"
        key = run.state["apiKeys"].get(agent["name"])
        if key and agent.get("apiKeyEnv"):
            exports.append(f"export {agent['apiKeyEnv']}='{key}'")
    out = STATE_DIR / "targets.yaml"
    if not run.dry_run:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        out.write_text(yaml.safe_dump(targets, sort_keys=False, allow_unicode=True))
        keys_file = STATE_DIR / "agent-keys.env"
        keys_file.write_text("\n".join([f"export AGORA_TARGETS='{out}'", *exports]) + "\n")
        keys_file.chmod(0o600)
        print(f"  wrote {out.relative_to(REPO)} and {keys_file.relative_to(REPO)}")
    return out


def step_evaluation(run: Run) -> None:
    evaluation.cmd_apply(run.api, None)


def step_portal(run: Run, serve: bool) -> None:
    portal = REPO / STACK["portal"]["path"]
    lines = ["# Written by deploy/bootstrap.py. Agents left out fall back to the scripted mock."]
    for spec in STACK["agents"]:
        url, key = run.state["invokeUrls"].get(spec["name"]), run.state["apiKeys"].get(spec["name"])
        if run.dry_run:
            url, key = url or f"<invoke URL of {spec['name']}>", key or "<API key>"
        if not (url and key):
            print(f"  {spec['name']}: no URL or key stored, the portal will use its mock for this agent")
            continue
        prefix = "VITE_AGENT_" + spec["portalKey"].replace("-", "_").upper()
        lines += [f"{prefix}_URL={url}", f"{prefix}_API_KEY={key}"]
    if run.dry_run:
        print(f"  would write {portal.name}/.env with {(len(lines) - 1) // 2} agent(s), then: npm install, npm run build")
        print(f"  would serve it at http://localhost:{STACK['portal']['port']}")
        return
    (portal / ".env").write_text("\n".join(lines) + "\n")
    (portal / ".env").chmod(0o600)
    if not (portal / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=portal, check=True)
    subprocess.run(["npm", "run", "build"], cwd=portal, check=True)
    port = str(STACK["portal"]["port"])
    print(f"\n  Portal built. The agents' API keys are inside the bundle: keep it on this machine.")
    if not serve:
        print(f"  Serve it with: (cd {portal.name} && npm run preview -- --port {port})")
        return
    print(f"  Serving http://localhost:{port}  (Ctrl+C to stop)")
    subprocess.run(["npm", "run", "preview", "--", "--port", port, "--strictPort"], cwd=portal, check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print every step and request, change nothing")
    parser.add_argument("--from", dest="start", choices=STEPS, help="resume from this step")
    parser.add_argument("--only", choices=STEPS, help="run just this step")
    parser.add_argument("--no-serve", action="store_true", help="build the portal but do not start serving it")
    args = parser.parse_args()

    run = Run(dry_run=args.dry_run)
    selected = [args.only] if args.only else STEPS[STEPS.index(args.start) if args.start else 0 :]
    handlers = {
        "preflight": step_preflight,
        "project": step_project,
        "mcp-servers": step_mcp_servers,
        "mcp-proxies": step_mcp_proxies,
        "agents": step_agents,
        "api-keys": step_api_keys,
        "evaluation": step_evaluation,
        "portal": lambda r: step_portal(r, serve=not args.no_serve),
    }
    for number, step in enumerate(STEPS, start=1):
        if step not in selected:
            continue
        say(f"Step {number}/{len(STEPS)}: {step}")
        handlers[step](run)
    if not args.dry_run and "api-keys" in selected:
        print("\nFor traffic and score checks in a new shell:  source deploy/.state/agent-keys.env")


if __name__ == "__main__":
    main()
