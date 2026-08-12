"""Namespace-partitioned, encrypted-at-rest document store for the Unified KB MCP Server.

Embedded local store (SQLite) — no external database, per PLAN.md §6. Document content is
encrypted at rest with Fernet (AES-128-CBC + HMAC) using a key that stands in for the
``amp:git-secret`` entry the Platform Admin would own in the real deployment. Search is a
simple keyword-overlap ranking rather than real embeddings — a deliberate simplification
(PLAN.md's open question on vector-store choice); it's enough to demonstrate namespace
isolation and tool behavior, which is the point of this server.
"""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


@dataclass
class Document:
    namespace: str
    doc_id: str
    source: str
    content: str
    created_at: float
    updated_at: float


class KBStore:
    """Encrypted, namespace-scoped document store backed by a local SQLite file."""

    def __init__(self, db_path: str, encryption_key: str) -> None:
        self._fernet = Fernet(encryption_key.encode())
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                namespace TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                source TEXT NOT NULL,
                content_enc BLOB NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (namespace, doc_id)
            )
            """
        )
        self._conn.commit()

    def _encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def _decrypt(self, ciphertext: bytes) -> str:
        try:
            return self._fernet.decrypt(bytes(ciphertext)).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeError("KB store content could not be decrypted — wrong encryption key?") from exc

    def upsert(self, namespace: str, doc_id: str, source: str, content: str) -> Document:
        now = time.time()
        row = self._conn.execute(
            "SELECT created_at FROM documents WHERE namespace = ? AND doc_id = ?",
            (namespace, doc_id),
        ).fetchone()
        created_at = row["created_at"] if row else now
        self._conn.execute(
            """
            INSERT INTO documents (namespace, doc_id, source, content_enc, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(namespace, doc_id) DO UPDATE SET
                source = excluded.source,
                content_enc = excluded.content_enc,
                updated_at = excluded.updated_at
            """,
            (namespace, doc_id, source, self._encrypt(content), created_at, now),
        )
        self._conn.commit()
        return Document(namespace, doc_id, source, content, created_at, now)

    def read(self, namespace: str, doc_id: str) -> Document | None:
        row = self._conn.execute(
            "SELECT * FROM documents WHERE namespace = ? AND doc_id = ?",
            (namespace, doc_id),
        ).fetchone()
        if row is None:
            return None
        return Document(
            namespace=row["namespace"],
            doc_id=row["doc_id"],
            source=row["source"],
            content=self._decrypt(row["content_enc"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_sources(self, namespace: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT source FROM documents WHERE namespace = ? ORDER BY source",
            (namespace,),
        ).fetchall()
        return [r["source"] for r in rows]

    def search(self, namespace: str, query: str, limit: int = 5) -> list[tuple[Document, float]]:
        query_terms = _tokenize(query)
        if not query_terms:
            return []
        rows = self._conn.execute(
            "SELECT * FROM documents WHERE namespace = ?",
            (namespace,),
        ).fetchall()
        scored: list[tuple[Document, float]] = []
        for row in rows:
            content = self._decrypt(row["content_enc"])
            doc_terms = _tokenize(f"{row['doc_id']} {row['source']} {content}")
            overlap = query_terms & doc_terms
            if not overlap:
                continue
            score = len(overlap) / len(query_terms)
            scored.append(
                (
                    Document(
                        namespace=row["namespace"],
                        doc_id=row["doc_id"],
                        source=row["source"],
                        content=content,
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    ),
                    score,
                )
            )
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:limit]

    def count(self, namespace: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM documents WHERE namespace = ?",
            (namespace,),
        ).fetchone()
        return int(row["n"])
