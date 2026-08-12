"""Loads fee schedules and permit applications from seed/*.json into the encrypted store.

Idempotent: fee schedules upsert by permit_type, applications upsert by permit_number — safe
to call on every server startup.
"""

from __future__ import annotations

import json
import os
import time

from store import FeeSchedule, PermitDBStore

SEED_DIR = os.path.join(os.path.dirname(__file__), "seed")


def seed_all(store: PermitDBStore) -> dict[str, int]:
    counts: dict[str, int] = {}

    with open(os.path.join(SEED_DIR, "fee_schedules.json"), encoding="utf-8") as f:
        fees = json.load(f)
    for fee in fees:
        store.upsert_fee_schedule(
            FeeSchedule(
                permit_type=fee["permit_type"],
                description=fee["description"],
                base_fee=fee["base_fee"],
                plan_check_fee=fee["plan_check_fee"],
                valuation_rate_per_1000=fee["valuation_rate_per_1000"],
                notes=fee.get("notes", ""),
            )
        )
    counts["fee_schedules"] = len(fees)

    with open(os.path.join(SEED_DIR, "permit_applications.json"), encoding="utf-8") as f:
        applications = json.load(f)
    now = time.time()
    for app in applications:
        submitted_at = now - app["submitted_days_ago"] * 86400
        store.seed_application(
            permit_number=app["permit_number"],
            permit_type=app["permit_type"],
            status=app["status"],
            applicant_name=app["applicant_name"],
            applicant_email=app["applicant_email"],
            applicant_phone=app["applicant_phone"],
            property_address=app["property_address"],
            valuation=app.get("valuation"),
            notes=app.get("notes", ""),
            submitted_at=submitted_at,
        )
    counts["permit_applications"] = len(applications)

    return counts


if __name__ == "__main__":
    from config import Config

    cfg = Config.from_env()
    store = PermitDBStore(cfg.db_path, cfg.encryption_key)
    result = seed_all(store)
    for name, n in result.items():
        print(f"{name}: {n} records seeded")
