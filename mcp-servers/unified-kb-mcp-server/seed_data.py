"""Loads seed KB articles from seed/*.json into the encrypted store, one namespace per file.

Idempotent: re-running upserts by (namespace, doc_id), so it's safe to call on every server
startup to guarantee the demo data is present.
"""

from __future__ import annotations

import json
import os

from config import NAMESPACES
from store import KBStore

SEED_DIR = os.path.join(os.path.dirname(__file__), "seed")


def seed_all(store: KBStore) -> dict[str, int]:
    counts: dict[str, int] = {}
    for namespace in NAMESPACES:
        path = os.path.join(SEED_DIR, f"{namespace}.json")
        if not os.path.exists(path):
            counts[namespace] = 0
            continue
        with open(path, encoding="utf-8") as f:
            docs = json.load(f)
        for doc in docs:
            store.upsert(
                namespace=namespace,
                doc_id=doc["doc_id"],
                source=doc["source"],
                content=doc["content"],
            )
        counts[namespace] = len(docs)
    return counts


if __name__ == "__main__":
    from config import Config

    cfg = Config.from_env()
    store = KBStore(cfg.db_path, cfg.encryption_key)
    result = seed_all(store)
    for ns, n in result.items():
        print(f"{ns}: {n} documents seeded")
