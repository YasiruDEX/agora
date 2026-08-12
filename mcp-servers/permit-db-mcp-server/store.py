"""Encrypted-at-rest store for permit applications and fee schedules.

Embedded local SQLite (PLAN.md §6) — applicant PII columns (name, email, phone) are
encrypted with Fernet, the same field-level simplification used by the Unified KB MCP Server
in place of SQLCipher (no working SQLCipher wheel for this environment; see that server's
README for the full rationale). Non-PII columns (permit_number, status, address, fee amounts)
are left in plaintext since they're needed for lookups/ordering without decrypting every row.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken


@dataclass
class PermitApplication:
    permit_number: str
    permit_type: str
    status: str
    applicant_name: str
    applicant_email: str
    applicant_phone: str
    property_address: str
    valuation: float | None
    submitted_at: float
    updated_at: float
    notes: str


@dataclass
class FeeSchedule:
    permit_type: str
    description: str
    base_fee: float
    plan_check_fee: float
    valuation_rate_per_1000: float
    notes: str


class PermitDBStore:
    def __init__(self, db_path: str, encryption_key: str) -> None:
        self._fernet = Fernet(encryption_key.encode())
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fee_schedules (
                permit_type TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                base_fee REAL NOT NULL,
                plan_check_fee REAL NOT NULL,
                valuation_rate_per_1000 REAL NOT NULL,
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS permit_applications (
                permit_number TEXT PRIMARY KEY,
                permit_type TEXT NOT NULL,
                status TEXT NOT NULL,
                applicant_name_enc BLOB NOT NULL,
                applicant_email_enc BLOB NOT NULL,
                applicant_phone_enc BLOB NOT NULL,
                property_address TEXT NOT NULL,
                valuation REAL,
                submitted_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._conn.commit()

    def _encrypt(self, value: str) -> bytes:
        return self._fernet.encrypt(value.encode("utf-8"))

    def _decrypt(self, value: bytes) -> str:
        try:
            return self._fernet.decrypt(bytes(value)).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeError("Permit DB content could not be decrypted — wrong encryption key?") from exc

    # -- fee schedules ----------------------------------------------------

    def upsert_fee_schedule(self, fee: FeeSchedule) -> None:
        self._conn.execute(
            """
            INSERT INTO fee_schedules (permit_type, description, base_fee, plan_check_fee, valuation_rate_per_1000, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(permit_type) DO UPDATE SET
                description = excluded.description,
                base_fee = excluded.base_fee,
                plan_check_fee = excluded.plan_check_fee,
                valuation_rate_per_1000 = excluded.valuation_rate_per_1000,
                notes = excluded.notes
            """,
            (
                fee.permit_type,
                fee.description,
                fee.base_fee,
                fee.plan_check_fee,
                fee.valuation_rate_per_1000,
                fee.notes,
            ),
        )
        self._conn.commit()

    def read_fee_schedule(self, permit_type: str) -> FeeSchedule | None:
        row = self._conn.execute(
            "SELECT * FROM fee_schedules WHERE permit_type = ?", (permit_type,)
        ).fetchone()
        if row is None:
            return None
        return FeeSchedule(
            permit_type=row["permit_type"],
            description=row["description"],
            base_fee=row["base_fee"],
            plan_check_fee=row["plan_check_fee"],
            valuation_rate_per_1000=row["valuation_rate_per_1000"],
            notes=row["notes"],
        )

    def list_permit_types(self) -> list[str]:
        rows = self._conn.execute("SELECT permit_type FROM fee_schedules ORDER BY permit_type").fetchall()
        return [r["permit_type"] for r in rows]

    def estimate_fee(self, permit_type: str, valuation: float | None) -> float | None:
        fee = self.read_fee_schedule(permit_type)
        if fee is None:
            return None
        total = fee.base_fee + fee.plan_check_fee
        if valuation and fee.valuation_rate_per_1000:
            total += (valuation / 1000.0) * fee.valuation_rate_per_1000
        return round(total, 2)

    # -- permit applications ------------------------------------------------

    def seed_application(
        self,
        permit_number: str,
        permit_type: str,
        status: str,
        applicant_name: str,
        applicant_email: str,
        applicant_phone: str,
        property_address: str,
        valuation: float | None,
        notes: str,
        submitted_at: float,
    ) -> None:
        now = submitted_at
        self._conn.execute(
            """
            INSERT INTO permit_applications
                (permit_number, permit_type, status, applicant_name_enc, applicant_email_enc,
                 applicant_phone_enc, property_address, valuation, submitted_at, updated_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(permit_number) DO UPDATE SET
                permit_type = excluded.permit_type,
                status = excluded.status,
                applicant_name_enc = excluded.applicant_name_enc,
                applicant_email_enc = excluded.applicant_email_enc,
                applicant_phone_enc = excluded.applicant_phone_enc,
                property_address = excluded.property_address,
                valuation = excluded.valuation,
                notes = excluded.notes
            """,
            (
                permit_number,
                permit_type,
                status,
                self._encrypt(applicant_name),
                self._encrypt(applicant_email),
                self._encrypt(applicant_phone),
                property_address,
                valuation,
                now,
                now,
                notes,
            ),
        )
        self._conn.commit()

    def create_application(
        self,
        permit_number: str,
        permit_type: str,
        applicant_name: str,
        applicant_email: str,
        applicant_phone: str,
        property_address: str,
        valuation: float | None,
    ) -> PermitApplication:
        now = time.time()
        self._conn.execute(
            """
            INSERT INTO permit_applications
                (permit_number, permit_type, status, applicant_name_enc, applicant_email_enc,
                 applicant_phone_enc, property_address, valuation, submitted_at, updated_at, notes)
            VALUES (?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, '')
            """,
            (
                permit_number,
                permit_type,
                self._encrypt(applicant_name),
                self._encrypt(applicant_email),
                self._encrypt(applicant_phone),
                property_address,
                valuation,
                now,
                now,
            ),
        )
        self._conn.commit()
        return PermitApplication(
            permit_number=permit_number,
            permit_type=permit_type,
            status="draft",
            applicant_name=applicant_name,
            applicant_email=applicant_email,
            applicant_phone=applicant_phone,
            property_address=property_address,
            valuation=valuation,
            submitted_at=now,
            updated_at=now,
            notes="",
        )

    def read_application(self, permit_number: str) -> PermitApplication | None:
        row = self._conn.execute(
            "SELECT * FROM permit_applications WHERE permit_number = ?", (permit_number,)
        ).fetchone()
        if row is None:
            return None
        return PermitApplication(
            permit_number=row["permit_number"],
            permit_type=row["permit_type"],
            status=row["status"],
            applicant_name=self._decrypt(row["applicant_name_enc"]),
            applicant_email=self._decrypt(row["applicant_email_enc"]),
            applicant_phone=self._decrypt(row["applicant_phone_enc"]),
            property_address=row["property_address"],
            valuation=row["valuation"],
            submitted_at=row["submitted_at"],
            updated_at=row["updated_at"],
            notes=row["notes"],
        )

    def next_permit_number(self, permit_type: str, year: int) -> str:
        prefix = "BP" if permit_type != "business_license" else "BL"
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM permit_applications WHERE permit_number LIKE ?",
            (f"{prefix}-{year}-%",),
        ).fetchone()
        seq = int(row["n"]) + 1
        return f"{prefix}-{year}-{seq:05d}"
