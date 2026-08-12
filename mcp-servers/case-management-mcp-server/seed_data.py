"""Loads citizen profiles, cases, and case notes from seed/*.json into the encrypted store.

Idempotent for citizens and cases (upsert by ID). Case notes are append-only in real usage,
so seeding checks whether any notes already exist for a case before re-inserting, to avoid
duplicating them on every restart.
"""

from __future__ import annotations

import json
import os
import time

from store import CaseManagementStore

SEED_DIR = os.path.join(os.path.dirname(__file__), "seed")


def seed_all(store: CaseManagementStore) -> dict[str, int]:
    counts: dict[str, int] = {}

    with open(os.path.join(SEED_DIR, "citizen_profiles.json"), encoding="utf-8") as f:
        citizens = json.load(f)
    for c in citizens:
        store.seed_citizen(
            citizen_id=c["citizen_id"],
            full_name=c["full_name"],
            date_of_birth=c["date_of_birth"],
            ssn_last4=c["ssn_last4"],
            address=c["address"],
            phone=c["phone"],
            email=c["email"],
            household_size=c["household_size"],
            notes=c.get("notes", ""),
        )
    counts["citizen_profiles"] = len(citizens)

    now = time.time()
    with open(os.path.join(SEED_DIR, "cases.json"), encoding="utf-8") as f:
        cases = json.load(f)
    for c in cases:
        store.seed_case(
            case_id=c["case_id"],
            citizen_id=c["citizen_id"],
            case_type=c["case_type"],
            status=c["status"],
            assigned_caseworker_id=c["assigned_caseworker_id"],
            summary=c["summary"],
            opened_at=now - c["opened_days_ago"] * 86400,
        )
    counts["cases"] = len(cases)

    with open(os.path.join(SEED_DIR, "case_notes.json"), encoding="utf-8") as f:
        notes = json.load(f)
    already_had_notes = {c["case_id"] for c in cases if store.list_notes(c["case_id"])}
    seeded_notes = 0
    for n in notes:
        if n["case_id"] in already_had_notes:
            continue
        store.add_note(case_id=n["case_id"], author=n["author"], content=n["content"])
        seeded_notes += 1
    counts["case_notes"] = seeded_notes

    return counts


if __name__ == "__main__":
    from config import Config

    cfg = Config.from_env()
    store = CaseManagementStore(cfg.db_path, cfg.encryption_key)
    result = seed_all(store)
    for name, n in result.items():
        print(f"{name}: {n} records seeded")
