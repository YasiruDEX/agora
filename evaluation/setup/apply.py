"""Apply the Agora evaluation setup to an Agent Manager organization.

    python evaluation/setup/apply.py plan       # print every request, change nothing
    python evaluation/setup/apply.py apply      # create or update evaluators, monitors, alerts
    python evaluation/setup/apply.py status     # latest mean scores and breached thresholds
    python evaluation/setup/apply.py backfill --hours 6   # one-off monitors over past traces
    python evaluation/setup/apply.py teardown   # delete the monitors and custom evaluators

Reads evaluators/evaluators.yaml, monitors/*.yaml and setup/targets.yaml. Safe to re-run:
existing evaluators and monitors are updated in place.

Environment:
    AMP_API_URL         Agent Manager API base, ending in /api/v1
    AMP_TOKEN           bearer token, or instead:
    AMP_TOKEN_URL, AMP_CLIENT_ID, AMP_CLIENT_SECRET   (OAuth2 client credentials)
    AMP_ALERT_WEBHOOK_URL   optional; see alertDestination.urlEnv in targets.yaml
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import string
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
EVALUATORS_FILE = ROOT / "evaluators" / "evaluators.yaml"
MONITORS_DIR = ROOT / "monitors"
TARGETS_FILE = Path(os.environ.get("AGORA_TARGETS", ROOT / "setup" / "targets.yaml"))


class Api:
    """Thin Agent Manager REST client. With dry_run, writes are printed instead of sent."""

    def __init__(self, dry_run: bool) -> None:
        self.dry_run = dry_run
        self.base = os.environ.get("AMP_API_URL", "").rstrip("/")
        self._token: str | None = os.environ.get("AMP_TOKEN")
        if not self.base and not dry_run:
            sys.exit("AMP_API_URL is not set (for example https://<host>/api/v1)")

    def _headers(self) -> dict[str, str]:
        if not self._token:
            needed = ("AMP_TOKEN_URL", "AMP_CLIENT_ID", "AMP_CLIENT_SECRET")
            missing = [n for n in needed if not os.environ.get(n)]
            if missing:
                sys.exit("Set AMP_TOKEN, or all of " + ", ".join(needed))
            resp = requests.post(
                os.environ["AMP_TOKEN_URL"],
                data={"grant_type": "client_credentials"},
                auth=(os.environ["AMP_CLIENT_ID"], os.environ["AMP_CLIENT_SECRET"]),
                timeout=30,
            )
            resp.raise_for_status()
            self._token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def read(self, path: str, params: dict | None = None) -> dict | None:
        """GET. Returns None on 404, and always None in a dry run with no API URL."""
        if self.dry_run and not self.base:
            return None
        resp = requests.get(self.base + path, headers=self._headers(), params=params, timeout=60)
        if resp.status_code == 404:
            return None
        _check(resp)
        return resp.json() if resp.content else {}

    def write(self, method: str, path: str, body: dict | None = None) -> dict:
        if self.dry_run:
            print(f"\n{method} {path}")
            if body is not None:
                print(json.dumps(_shorten(body), indent=2, ensure_ascii=False))
            return {}
        resp = requests.request(method, self.base + path, headers=self._headers(), json=body, timeout=120)
        _check(resp)
        print(f"  {method} {path} -> {resp.status_code}")
        return resp.json() if resp.content else {}


def _check(resp: requests.Response) -> None:
    if resp.status_code >= 400:
        sys.exit(f"{resp.request.method} {resp.url} failed: {resp.status_code} {resp.text[:600]}")


def _shorten(body: dict) -> dict:
    """Keep dry-run output readable: show evaluator source as a size, not the whole file."""
    if isinstance(body.get("source"), str) and len(body["source"]) > 200:
        body = dict(body, source=f"<{len(body['source'])} characters from sourceFile>")
    return body


def _seg(value: str) -> str:
    return quote(value, safe="")


def _fill(node, variables: dict):
    """Replace ${name} placeholders in every string of a nested structure."""
    if isinstance(node, str):
        return string.Template(node).substitute(variables)
    if isinstance(node, list):
        return [_fill(item, variables) for item in node]
    if isinstance(node, dict):
        return {key: _fill(value, variables) for key, value in node.items()}
    return node


def load_targets() -> dict:
    return yaml.safe_load(TARGETS_FILE.read_text())


def load_evaluators() -> list[dict]:
    """Custom evaluator create/update bodies, with source read from each sourceFile."""
    bodies = []
    for entry in yaml.safe_load(EVALUATORS_FILE.read_text())["evaluators"]:
        body = {k: v for k, v in entry.items() if k != "sourceFile"}
        body["description"] = " ".join(str(body.get("description", "")).split())
        body["source"] = (EVALUATORS_FILE.parent / entry["sourceFile"]).read_text()
        bodies.append(body)
    return bodies


def load_monitors(targets: dict) -> list[dict]:
    """One entry per (agent instance, monitor): the create body plus its alert settings."""
    by_kind = {}
    for path in sorted(MONITORS_DIR.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        by_kind[doc["appliesTo"]] = doc["monitors"]

    custom_judges = {e["identifier"] for e in load_evaluators() if e["type"] == "llm_judge"}
    planned = []
    for agent in targets["agents"]:
        if agent["kind"] not in by_kind:
            sys.exit(f"No monitors file with appliesTo: {agent['kind']} (agent {agent['name']})")
        for template in by_kind[agent["kind"]]:
            monitor = _fill(copy.deepcopy(template), agent.get("vars") or {})
            alerts = monitor.pop("alerts", None)
            uses_judge = False
            for evaluator in monitor["evaluators"]:
                is_judge = evaluator.pop("judge", False) or evaluator["identifier"] in custom_judges
                if is_judge:
                    uses_judge = True
                    evaluator.setdefault("config", {}).setdefault("model", targets["judgeModel"])
            monitor["environmentName"] = targets["environment"]
            if uses_judge:
                monitor["llmProvider"] = {"providerName": targets["llmProvider"]}
            _validate(agent["name"], monitor, alerts)
            planned.append({"agent": agent["name"], "monitor": monitor, "alerts": alerts})
    return planned


def _validate(agent: str, monitor: dict, alerts: dict | None) -> None:
    """Catch the mistakes Agent Manager would reject, before any request is sent."""
    where = f"{agent}/{monitor['name']}"
    if monitor["type"] == "future" and monitor.get("intervalMinutes", 60) < 5:
        sys.exit(f"{where}: intervalMinutes must be at least 5")
    if not 0 < monitor.get("samplingRate", 1.0) <= 1:
        sys.exit(f"{where}: samplingRate must be above 0 and at most 1")
    names = [e["displayName"] for e in monitor["evaluators"]]
    if len(set(names)) != len(names):
        sys.exit(f"{where}: evaluator display names must be unique")
    thresholds = (alerts or {}).get("thresholds", [])
    if len(thresholds) > 20:
        sys.exit(f"{where}: at most 20 thresholds per monitor")
    for t in thresholds:
        if t["evaluator"] not in names:
            sys.exit(f"{where}: threshold names '{t['evaluator']}', which is not an evaluator of this monitor")
        if t["operator"] not in ("below", "above") or not 0 <= t["value"] <= 1:
            sys.exit(f"{where}: threshold on '{t['evaluator']}' needs operator below|above and a value from 0 to 1")


def _monitors_path(targets: dict, agent: str) -> str:
    return f"/orgs/{_seg(targets['org'])}/projects/{_seg(targets['project'])}/agents/{_seg(agent)}/monitors"


def ensure_destination(api: Api, targets: dict) -> str | None:
    """Return the alert destination's id, creating it if needed. None means: skip alerts."""
    spec = targets.get("alertDestination")
    if not spec:
        return None
    base = f"/orgs/{_seg(targets['org'])}/events/destinations"
    listing = api.read(base) or {}
    for item in listing.get("destinations") or listing.get("items") or []:
        if item.get("name", "").lower() == spec["name"].lower():
            return item["id"]
    url = os.environ.get(spec["urlEnv"], "")
    if not url:
        if api.dry_run:
            url = f"<value of ${spec['urlEnv']}>"
        else:
            print(f"  {spec['urlEnv']} is not set and no destination named '{spec['name']}' exists: skipping alerts")
            return None
    config = {"url": url}
    if spec["kind"] == "notify":
        config["service"] = spec["service"]
    created = api.write(
        "POST",
        base,
        {
            "name": spec["name"],
            "description": spec.get("description", ""),
            "kind": spec["kind"],
            "config": config,
            "availability": "all",
        },
    )
    return created.get("id", "<new destination id>")


def cmd_apply(api: Api, _args) -> None:
    targets = load_targets()
    org = _seg(targets["org"])

    print("== Custom evaluators ==")
    for body in load_evaluators():
        path = f"/orgs/{org}/evaluators/custom/{_seg(body['identifier'])}"
        if api.read(path) is None:
            api.write("POST", f"/orgs/{org}/evaluators/custom", body)
        else:
            update = {k: v for k, v in body.items() if k not in ("identifier", "type", "level")}
            api.write("PUT", path, update)

    print("\n== Alert destination ==")
    destination_id = ensure_destination(api, targets)

    print("\n== Monitors and thresholds ==")
    for item in load_monitors(targets):
        monitor, base = item["monitor"], _monitors_path(targets, item["agent"])
        path = f"{base}/{_seg(monitor['name'])}"
        if api.read(path) is None:
            api.write("POST", base, monitor)
        else:
            keep = ("displayName", "evaluators", "llmProvider", "intervalMinutes", "samplingRate")
            api.write("PATCH", path, {k: monitor[k] for k in keep if k in monitor})
        if item["alerts"] and destination_id:
            alert = {
                "destinationIds": [destination_id],
                "notifyOnFailure": item["alerts"].get("notifyOnFailure", True),
                "notifyOnSuccess": item["alerts"].get("notifyOnSuccess", False),
                "thresholds": [dict(t, aggregation="mean") for t in item["alerts"].get("thresholds", [])],
            }
            api.write("PUT", f"{path}/alerting", alert)


def cmd_backfill(api: Api, args) -> None:
    """Create one-off 'past' monitors over the last N hours, for a before/after comparison."""
    targets = load_targets()
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(hours=args.hours)
    stamp = end.strftime("%m%d-%H%M")
    for item in load_monitors(targets):
        if args.agent and item["agent"] != args.agent:
            continue
        monitor = dict(item["monitor"])
        monitor.pop("intervalMinutes", None)
        monitor.update(
            name=f"{monitor['name']}-bf-{stamp}"[:60],
            displayName=f"{monitor['displayName']} (last {args.hours:g}h, {stamp})",
            type="past",
            traceStart=start.isoformat().replace("+00:00", "Z"),
            traceEnd=end.isoformat().replace("+00:00", "Z"),
        )
        api.write("POST", _monitors_path(targets, item["agent"]), monitor)


def cmd_status(api: Api, args) -> None:
    targets = load_targets()
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=args.hours)
    window = {"startTime": start.isoformat().replace("+00:00", "Z"), "endTime": end.isoformat().replace("+00:00", "Z")}
    for item in load_monitors(targets):
        path = f"{_monitors_path(targets, item['agent'])}/{_seg(item['monitor']['name'])}"
        scores = api.read(f"{path}/scores", window)
        print(f"\n{item['agent']} / {item['monitor']['displayName']}")
        if scores is None:
            print("  monitor not found")
            continue
        limits = {t["evaluator"]: t for t in (item["alerts"] or {}).get("thresholds", [])}
        breached = {t["evaluator"] for t in (api.read(f"{path}/alerting") or {}).get("breached") or []}
        for row in scores.get("evaluators", []):
            mean = (row.get("aggregations") or {}).get("mean")
            name = row["evaluatorName"]
            limit = limits.get(name)
            rule = f"{limit['operator']} {limit['value']:.2f}" if limit else "-"
            flag = "BREACHED" if name in breached else ""
            shown = f"{mean:.2f}" if isinstance(mean, (int, float)) else "  - "
            print(f"  {name:<28} mean {shown}  n={row.get('count', 0):<4} skipped={row.get('skippedCount', 0):<4} alert: {rule:<11} {flag}")


def cmd_teardown(api: Api, _args) -> None:
    targets = load_targets()
    for item in load_monitors(targets):
        path = f"{_monitors_path(targets, item['agent'])}/{_seg(item['monitor']['name'])}"
        if api.dry_run or api.read(path) is not None:
            api.write("DELETE", path)
    for body in load_evaluators():
        path = f"/orgs/{_seg(targets['org'])}/evaluators/custom/{_seg(body['identifier'])}"
        if api.dry_run or api.read(path) is not None:
            api.write("DELETE", path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    sub.add_parser("apply")
    status = sub.add_parser("status")
    status.add_argument("--hours", type=float, default=1)
    backfill = sub.add_parser("backfill")
    backfill.add_argument("--hours", type=float, default=6)
    backfill.add_argument("--agent", help="only this agent (name from targets.yaml)")
    backfill.add_argument("--dry-run", action="store_true")
    teardown = sub.add_parser("teardown")
    teardown.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.command == "plan":
        cmd_apply(Api(dry_run=True), args)
    elif args.command == "apply":
        cmd_apply(Api(dry_run=False), args)
    elif args.command == "status":
        cmd_status(Api(dry_run=False), args)
    elif args.command == "backfill":
        cmd_backfill(Api(dry_run=args.dry_run), args)
    elif args.command == "teardown":
        cmd_teardown(Api(dry_run=args.dry_run), args)


if __name__ == "__main__":
    main()
