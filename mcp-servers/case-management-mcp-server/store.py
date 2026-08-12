"""Encrypted-at-rest store for case records, case notes, and citizen profiles.

Embedded local SQLite (PLAN.md §6) — citizen PII (name, DOB, SSN last 4, address, phone,
email) and case note content are encrypted with Fernet, the same field-level simplification
used by the other two dedicated MCP servers in place of SQLCipher.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken


@dataclass
class Case:
    case_id: str
    citizen_id: str
    case_type: str
    status: str
    assigned_caseworker_id: str
    summary: str
    opened_at: float
    updated_at: float


@dataclass
class CaseNote:
    note_id: int
    case_id: str
    author: str
    content: str
    created_at: float


@dataclass
class CitizenProfile:
    citizen_id: str
    full_name: str
    date_of_birth: str
    ssn_last4: str
    address: str
    phone: str
    email: str
    household_size: int
    notes: str


class CaseManagementStore:
    def __init__(self, db_path: str, encryption_key: str) -> None:
        self._fernet = Fernet(encryption_key.encode())
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS citizen_profiles (
                citizen_id TEXT PRIMARY KEY,
                full_name_enc BLOB NOT NULL,
                date_of_birth_enc BLOB NOT NULL,
                ssn_last4_enc BLOB NOT NULL,
                address_enc BLOB NOT NULL,
                phone_enc BLOB NOT NULL,
                email_enc BLOB NOT NULL,
                household_size INTEGER NOT NULL,
                notes_enc BLOB NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                citizen_id TEXT NOT NULL,
                case_type TEXT NOT NULL,
                status TEXT NOT NULL,
                assigned_caseworker_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                opened_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS case_notes (
                note_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                author TEXT NOT NULL,
                content_enc BLOB NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )
        self._conn.commit()

    def _encrypt(self, value: str) -> bytes:
        return self._fernet.encrypt(value.encode("utf-8"))

    def _decrypt(self, value: bytes) -> str:
        try:
            return self._fernet.decrypt(bytes(value)).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeError("Case Management content could not be decrypted — wrong encryption key?") from exc

    # -- citizen profiles ---------------------------------------------------

    def seed_citizen(
        self,
        citizen_id: str,
        full_name: str,
        date_of_birth: str,
        ssn_last4: str,
        address: str,
        phone: str,
        email: str,
        household_size: int,
        notes: str,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO citizen_profiles
                (citizen_id, full_name_enc, date_of_birth_enc, ssn_last4_enc, address_enc,
                 phone_enc, email_enc, household_size, notes_enc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(citizen_id) DO UPDATE SET
                full_name_enc = excluded.full_name_enc,
                date_of_birth_enc = excluded.date_of_birth_enc,
                ssn_last4_enc = excluded.ssn_last4_enc,
                address_enc = excluded.address_enc,
                phone_enc = excluded.phone_enc,
                email_enc = excluded.email_enc,
                household_size = excluded.household_size,
                notes_enc = excluded.notes_enc
            """,
            (
                citizen_id,
                self._encrypt(full_name),
                self._encrypt(date_of_birth),
                self._encrypt(ssn_last4),
                self._encrypt(address),
                self._encrypt(phone),
                self._encrypt(email),
                household_size,
                self._encrypt(notes),
            ),
        )
        self._conn.commit()

    def read_citizen(self, citizen_id: str) -> CitizenProfile | None:
        row = self._conn.execute(
            "SELECT * FROM citizen_profiles WHERE citizen_id = ?", (citizen_id,)
        ).fetchone()
        if row is None:
            return None
        return CitizenProfile(
            citizen_id=row["citizen_id"],
            full_name=self._decrypt(row["full_name_enc"]),
            date_of_birth=self._decrypt(row["date_of_birth_enc"]),
            ssn_last4=self._decrypt(row["ssn_last4_enc"]),
            address=self._decrypt(row["address_enc"]),
            phone=self._decrypt(row["phone_enc"]),
            email=self._decrypt(row["email_enc"]),
            household_size=row["household_size"],
            notes=self._decrypt(row["notes_enc"]),
        )

    def update_citizen_fields(self, citizen_id: str, **fields: str) -> CitizenProfile | None:
        existing = self.read_citizen(citizen_id)
        if existing is None:
            return None
        merged = {
            "full_name": fields.get("full_name", existing.full_name),
            "date_of_birth": fields.get("date_of_birth", existing.date_of_birth),
            "ssn_last4": fields.get("ssn_last4", existing.ssn_last4),
            "address": fields.get("address", existing.address),
            "phone": fields.get("phone", existing.phone),
            "email": fields.get("email", existing.email),
            "notes": fields.get("notes", existing.notes),
        }
        self.seed_citizen(citizen_id, household_size=existing.household_size, **merged)
        return self.read_citizen(citizen_id)

    # -- cases ---------------------------------------------------------------

    def seed_case(
        self,
        case_id: str,
        citizen_id: str,
        case_type: str,
        status: str,
        assigned_caseworker_id: str,
        summary: str,
        opened_at: float,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO cases
                (case_id, citizen_id, case_type, status, assigned_caseworker_id, summary, opened_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id) DO UPDATE SET
                citizen_id = excluded.citizen_id,
                case_type = excluded.case_type,
                status = excluded.status,
                assigned_caseworker_id = excluded.assigned_caseworker_id,
                summary = excluded.summary
            """,
            (case_id, citizen_id, case_type, status, assigned_caseworker_id, summary, opened_at, opened_at),
        )
        self._conn.commit()

    def _row_to_case(self, row: sqlite3.Row) -> Case:
        return Case(
            case_id=row["case_id"],
            citizen_id=row["citizen_id"],
            case_type=row["case_type"],
            status=row["status"],
            assigned_caseworker_id=row["assigned_caseworker_id"],
            summary=row["summary"],
            opened_at=row["opened_at"],
            updated_at=row["updated_at"],
        )

    def read_case(self, case_id: str) -> Case | None:
        row = self._conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        return self._row_to_case(row) if row else None

    def search_cases(self, caseworker_id: str, query: str = "") -> list[Case]:
        rows = self._conn.execute(
            "SELECT * FROM cases WHERE assigned_caseworker_id = ? ORDER BY updated_at DESC",
            (caseworker_id,),
        ).fetchall()
        cases = [self._row_to_case(r) for r in rows]
        if not query.strip():
            return cases
        terms = query.strip().lower()
        return [
            c
            for c in cases
            if terms in c.case_type.lower() or terms in c.summary.lower() or terms in c.status.lower()
        ]

    def update_status(self, case_id: str, new_status: str) -> Case | None:
        if self.read_case(case_id) is None:
            return None
        self._conn.execute(
            "UPDATE cases SET status = ?, updated_at = ? WHERE case_id = ?",
            (new_status, time.time(), case_id),
        )
        self._conn.commit()
        return self.read_case(case_id)

    def close_case(self, case_id: str) -> Case | None:
        return self.update_status(case_id, "closed")

    # -- case notes ------------------------------------------------------------

    def add_note(self, case_id: str, author: str, content: str) -> CaseNote:
        now = time.time()
        cur = self._conn.execute(
            "INSERT INTO case_notes (case_id, author, content_enc, created_at) VALUES (?, ?, ?, ?)",
            (case_id, author, self._encrypt(content), now),
        )
        self._conn.execute("UPDATE cases SET updated_at = ? WHERE case_id = ?", (now, case_id))
        self._conn.commit()
        return CaseNote(note_id=cur.lastrowid, case_id=case_id, author=author, content=content, created_at=now)

    def list_notes(self, case_id: str) -> list[CaseNote]:
        rows = self._conn.execute(
            "SELECT * FROM case_notes WHERE case_id = ? ORDER BY created_at ASC", (case_id,)
        ).fetchall()
        return [
            CaseNote(
                note_id=r["note_id"],
                case_id=r["case_id"],
                author=r["author"],
                content=self._decrypt(r["content_enc"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]
