"""Send realistic resident traffic to the Agora agents so the monitors have traces to score.

    python evaluation/traffic/run.py --list
    python evaluation/traffic/run.py                         # every agent, one pass
    python evaluation/traffic/run.py --agent citizen-inquiry-social-services --rounds 3
    python evaluation/traffic/run.py --category out-of-scope --delay 2
    python evaluation/traffic/run.py --id ss-pii-echo         # one scenario, for a live demo

Agents, invoke URLs and API-key env vars come from setup/targets.yaml. Scenarios come from
traffic/scenarios/<set>.yaml. Each request is a new conversation (fresh session_id), so each
one becomes one trace.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
import uuid
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
TARGETS_FILE = Path(os.environ.get("AGORA_TARGETS", ROOT / "setup" / "targets.yaml"))
SCENARIOS_DIR = ROOT / "traffic" / "scenarios"
API_KEY_HEADER = os.environ.get("AGORA_API_KEY_HEADER", "X-API-Key")


def load_plan(args) -> list[tuple[dict, dict]]:
    """(agent, scenario) pairs after applying the --agent, --category and --id filters."""
    plan = []
    for agent in yaml.safe_load(TARGETS_FILE.read_text())["agents"]:
        if not agent.get("scenarios") or (args.agent and agent["name"] != args.agent):
            continue
        scenarios = yaml.safe_load((SCENARIOS_DIR / f"{agent['scenarios']}.yaml").read_text())["scenarios"]
        for scenario in scenarios:
            if args.category and scenario["category"] != args.category:
                continue
            if args.id and scenario["id"] != args.id:
                continue
            plan.append((agent, scenario))
    return plan


def send(agent: dict, scenario: dict, timeout: float) -> tuple[bool, float, str]:
    headers = {"Content-Type": "application/json"}
    key = os.environ.get(agent.get("apiKeyEnv") or "", "")
    if key:
        headers[API_KEY_HEADER] = key
    body = {"message": " ".join(scenario["message"].split()), "session_id": f"traffic-{uuid.uuid4()}"}
    started = time.monotonic()
    try:
        resp = requests.post(agent["invokeUrl"], json=body, headers=headers, timeout=timeout)
        elapsed = time.monotonic() - started
        if resp.status_code >= 400:
            return False, elapsed, f"HTTP {resp.status_code}: {resp.text[:160]}"
        return True, elapsed, str(resp.json().get("response", ""))
    except requests.RequestException as exc:
        return False, time.monotonic() - started, f"{type(exc).__name__}: {exc}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", help="only this agent (name from targets.yaml)")
    parser.add_argument("--category", help="only scenarios in this category")
    parser.add_argument("--id", help="only the scenario with this id")
    parser.add_argument("--rounds", type=int, default=1, help="passes over the selected scenarios")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--no-shuffle", action="store_true", help="keep file order")
    parser.add_argument("--list", action="store_true", help="print the selected scenarios and exit")
    args = parser.parse_args()

    plan = load_plan(args)
    if not plan:
        sys.exit("No scenarios match those filters.")
    if args.list:
        for agent, scenario in plan:
            print(f"{agent['name']:<36} {scenario['category']:<13} {scenario['id']:<24} watch: {', '.join(scenario.get('watch', []))}")
        return

    failures = 0
    for round_no in range(1, args.rounds + 1):
        batch = list(plan)
        if not args.no_shuffle:
            random.shuffle(batch)
        for agent, scenario in batch:
            ok, elapsed, text = send(agent, scenario, args.timeout)
            failures += not ok
            mark = "ok  " if ok else "FAIL"
            print(f"[{round_no}/{args.rounds}] {mark} {elapsed:5.1f}s {agent['name']} / {scenario['id']}")
            print("        " + " ".join(text.split())[:200])
            time.sleep(args.delay)
    total = len(plan) * args.rounds
    print(f"\nSent {total} request(s), {failures} failed.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
