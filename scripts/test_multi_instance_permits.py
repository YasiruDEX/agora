"""Verify the Permit & Licensing Agent codebase can run as two independent,
concurrently-running instances (Building Permits on :8002, Business Licenses
on :8003), each backed by its own isolated SQLite database via PERMIT_DB_PATH.

Boots both instances as subprocesses, polls /health, sends a /chat request to
each with a NIC that only exists in that instance's own database, checks that
each instance answers correctly from its own data and cannot see the other
instance's records, then tears both down.

Usage:
    ./.venv/bin/python scripts/test_multi_instance_permits.py
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
AGENT_MODULE = "agents.permit_licensing_agent.main"

INSTANCES = [
    {
        "name": "Building Permits",
        "env_file": ".env.building_permits",
        "port": 8002,
        "db_path": REPO_ROOT / "data" / "building_permits.db",
        "own_nic": "DL-A4521987",
        "own_app_id": "APP-BP-5001",
        "own_name_fragment": "Anderson",
        "foreign_nic": "DL-C99012300",
        "foreign_app_id": "APP-TL-6001",
    },
    {
        "name": "Business Licenses",
        "env_file": ".env.business_licenses",
        "port": 8003,
        "db_path": REPO_ROOT / "data" / "business_licenses.db",
        "own_nic": "DL-C99012300",
        "own_app_id": "APP-TL-6001",
        "own_name_fragment": "Mitchell",
        "foreign_nic": "DL-A4521987",
        "foreign_app_id": "APP-BP-5001",
    },
]

HEALTH_TIMEOUT_SECONDS = 30
CHAT_TIMEOUT_SECONDS = 60

results: list[tuple[str, bool, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    results.append((label, condition, detail))


def wait_for_health(port: int, timeout: int) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(f"http://localhost:{port}/health", timeout=2.0)
            if resp.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(1)
    return False


def launch_instance(instance: dict, log_path: Path) -> subprocess.Popen:
    for stale in (instance["db_path"],):
        stale.unlink(missing_ok=True)

    env = {**os.environ, "AGENT_ENV_FILE": instance["env_file"]}
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        [str(VENV_PYTHON), "-m", AGENT_MODULE],
        cwd=REPO_ROOT,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    proc._log_file = log_file  # keep a handle so we can close it on teardown
    return proc


def main() -> int:
    print("=== Multi-instance verification: Permit & Licensing Agent ===\n")

    procs: list[subprocess.Popen] = []
    try:
        print("--- Booting both instances concurrently ---")
        for instance in INSTANCES:
            log_path = Path(f"/tmp/permit_instance_{instance['port']}.log")
            proc = launch_instance(instance, log_path)
            procs.append(proc)
            print(f"  Launched '{instance['name']}' (pid={proc.pid}) targeting port {instance['port']}, "
                  f"logging to {log_path}")

        print("\n--- Waiting for both instances to become healthy ---")
        for instance, proc in zip(INSTANCES, procs):
            healthy = wait_for_health(instance["port"], HEALTH_TIMEOUT_SECONDS)
            check(f"{instance['name']} healthy on port {instance['port']}", healthy)
            if not healthy:
                print(f"    (see /tmp/permit_instance_{instance['port']}.log for startup output)")

        print("\n--- Confirming both processes are alive simultaneously (no port collision) ---")
        both_alive = all(proc.poll() is None for proc in procs)
        check("Both instances still running concurrently", both_alive)

        print("\n--- Confirming distinct SQLite database files were created ---")
        for instance in INSTANCES:
            exists = instance["db_path"].exists()
            check(f"{instance['name']} created its own DB at {instance['db_path'].relative_to(REPO_ROOT)}", exists)
        if INSTANCES[0]["db_path"].exists() and INSTANCES[1]["db_path"].exists():
            distinct_files = INSTANCES[0]["db_path"].resolve() != INSTANCES[1]["db_path"].resolve()
            check("The two database files are distinct paths", distinct_files)

        print("\n--- Querying each instance for its OWN citizen's application ---")
        for instance in INSTANCES:
            resp = httpx.post(
                f"http://localhost:{instance['port']}/chat",
                json={
                    "message": (
                        f"Look up the application for NIC {instance['own_nic']} and tell me its "
                        "application ID, its current status, and the full name on file for that applicant."
                    ),
                    "session_id": f"multi-instance-test-{instance['port']}",
                    "context": {},
                },
                timeout=CHAT_TIMEOUT_SECONDS,
            )
            check(f"{instance['name']} /chat returned HTTP 200", resp.status_code == 200, f"got {resp.status_code}")
            answer = resp.json().get("response", "") if resp.status_code == 200 else ""
            print(f"    {instance['name']} answer: {answer!r}")
            check(
                f"{instance['name']} answer references its own app_id ({instance['own_app_id']})",
                instance["own_app_id"] in answer,
            )
            check(
                f"{instance['name']} answer references its own applicant name ({instance['own_name_fragment']})",
                instance["own_name_fragment"] in answer,
            )

        print("\n--- Confirming database isolation (each instance is blind to the other's NIC) ---")
        for instance in INSTANCES:
            resp = httpx.post(
                f"http://localhost:{instance['port']}/chat",
                json={
                    "message": f"What is the status of the application for NIC {instance['foreign_nic']}?",
                    "session_id": f"multi-instance-isolation-{instance['port']}",
                    "context": {},
                },
                timeout=CHAT_TIMEOUT_SECONDS,
            )
            answer = resp.json().get("response", "") if resp.status_code == 200 else ""
            print(f"    {instance['name']} answer for foreign NIC {instance['foreign_nic']}: {answer!r}")
            # Echoing the queried NIC back in a "not found" message is expected and fine;
            # what must NOT happen is the other instance's actual application data leaking
            # through (its app_id), which would prove the databases aren't really isolated.
            check(
                f"{instance['name']} does NOT leak the other instance's app_id ({instance['foreign_app_id']})",
                instance["foreign_app_id"] not in answer,
            )

    finally:
        print("\n--- Tearing down both instances ---")
        for proc in procs:
            proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
            log_file = getattr(proc, "_log_file", None)
            if log_file:
                log_file.close()
        print("Both instances stopped.")

    print("\n=== Summary ===")
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for label, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    print(f"\n{passed}/{total} checks passed.")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
