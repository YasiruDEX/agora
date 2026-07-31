"""MCP stdio server exposing CRUD + PII redaction tools over data/records_compliance.db.

Table and column names are validated against a fixed schema whitelist before
being interpolated into SQL — only values are ever passed as bind parameters.

NOTE ON DISCLOSURE CONTROL: this server has no notion of exemption policy or
redaction rules on its own — `db_read_record` will happily return a record's
raw, unredacted `raw_content` including any exemption flag. Statutory
exemption checking and PII redaction are enforced one layer up, in
agents/records_foia_agent/graph.py, which wraps this data access into
`get_public_record` so the LLM never reaches raw_content directly.
"""
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_db_path() -> Path:
    """Configurable via RECORDS_DB_PATH so this server also works bundled
    standalone alongside a single agent, without the rest of the monorepo."""
    raw_path = os.environ.get("RECORDS_DB_PATH", str(REPO_ROOT / "data" / "records_compliance.db"))
    path = Path(raw_path)
    return path if path.is_absolute() else (REPO_ROOT / path)


DB_PATH = _resolve_db_path()

SCHEMA: dict[str, dict[str, Any]] = {
    "public_records": {
        "columns": ["record_id", "title", "category", "raw_content", "is_exempt", "exemption_reason", "created_at"],
        "primary_key": "record_id",
    },
    "foia_requests": {
        "columns": [
            "request_id",
            "requester_name",
            "requester_email",
            "requested_category",
            "status",
            "released_content",
            "created_at",
        ],
        "primary_key": "request_id",
    },
}

SEED_PUBLIC_RECORDS = [
    (
        "REC-2026-101",
        "2025 City Center Maintenance Contract",
        "MUNICIPAL_CONTRACT",
        "Contractor: Apex Ltd. Total: $450,000. Contact: john.doe@apex.com, Phone: 555-0199. SSN: 000-12-3456.",
        0,
        None,
    ),
    (
        "REC-2026-102",
        "Internal Investigation on Property Zone 4",
        "INTERNAL_MEMO",
        "Ongoing internal investigation regarding building code violations...",
        1,
        "Statutory Exemption 7(A) - Pending Law Enforcement Investigation",
    ),
]

# Order matters: redact the most specific pattern (SSN) first, since its
# already-redacted "[REDACTED PII]" text will not accidentally match the
# broader phone/email patterns run afterward.
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_RE = re.compile(r"\b\d{3}-\d{4}\b|\b0\d{9}\b|\+94\d{9}\b")
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]+")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS public_records (
                record_id TEXT PRIMARY KEY,
                title TEXT,
                category TEXT,
                raw_content TEXT,
                is_exempt BOOLEAN,
                exemption_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS foia_requests (
                request_id TEXT PRIMARY KEY,
                requester_name TEXT,
                requester_email TEXT,
                requested_category TEXT,
                status TEXT,
                released_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if conn.execute("SELECT COUNT(*) FROM public_records").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO public_records "
                "(record_id, title, category, raw_content, is_exempt, exemption_reason) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                SEED_PUBLIC_RECORDS,
            )
        conn.commit()
    finally:
        conn.close()


def _validate_table(table_name: str) -> dict[str, Any]:
    if table_name not in SCHEMA:
        raise ValueError(f"Unknown table '{table_name}'. Valid tables: {list(SCHEMA.keys())}")
    return SCHEMA[table_name]


def _filter_columns(table_name: str, data: dict[str, Any]) -> dict[str, Any]:
    valid_columns = set(SCHEMA[table_name]["columns"])
    unknown = set(data.keys()) - valid_columns
    if unknown:
        raise ValueError(f"Unknown column(s) {sorted(unknown)} for table '{table_name}'. Valid: {sorted(valid_columns)}")
    return data


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


init_db()

# MCP_TRANSPORT selects "stdio" (default, for local subprocess use) or "sse"/
# "streamable-http" to run this as a standalone network service that agents
# connect to remotely via MCP_*_URL env vars instead of spawning it locally.
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "9007"))

mcp = FastMCP("records-db", host=MCP_HOST, port=MCP_PORT)


@mcp.tool()
def db_read_record(table_name: str, query_params: dict[str, Any]) -> str:
    """Fetch rows from 'public_records' or 'foia_requests' matching query_params.

    Args:
        table_name: 'public_records' or 'foia_requests'.
        query_params: Column-value pairs to filter by (e.g. {"record_id": "REC-2026-101"}).
            Pass an empty dict to fetch all rows (capped at 50).
    """
    _validate_table(table_name)
    filters = _filter_columns(table_name, query_params)

    sql = f"SELECT * FROM {table_name}"
    params: list[Any] = []
    if filters:
        where_clause = " AND ".join(f"{col} = ?" for col in filters)
        sql += f" WHERE {where_clause}"
        params = list(filters.values())
    sql += " LIMIT 50"

    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        results = [_row_to_dict(r) for r in rows]
        if not results:
            return f"No rows found in '{table_name}' matching {query_params}."
        return json.dumps(results, default=str)
    finally:
        conn.close()


@mcp.tool()
def db_create_record(table_name: str, record_data: dict[str, Any]) -> str:
    """Insert a new row into 'public_records' or 'foia_requests'.

    Args:
        table_name: 'public_records' or 'foia_requests'.
        record_data: Column-value pairs to insert. Must match the table's schema.
    """
    _validate_table(table_name)
    data = _filter_columns(table_name, record_data)
    if not data:
        return "ERROR: record_data must contain at least one column."

    columns = list(data.keys())
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"

    conn = _connect()
    try:
        conn.execute(sql, [data[c] for c in columns])
        conn.commit()
        return f"OK: inserted 1 row into '{table_name}'."
    except sqlite3.IntegrityError as e:
        return f"ERROR: {e}"
    finally:
        conn.close()


@mcp.tool()
def db_update_record(table_name: str, key_field: str, key_value: str, update_data: dict[str, Any]) -> str:
    """Update an existing row in 'public_records' or 'foia_requests'.

    Args:
        table_name: 'public_records' or 'foia_requests'.
        key_field: Column used to identify the row (typically the primary key).
        key_value: Value of key_field identifying the row to update.
        update_data: Column-value pairs to set.
    """
    schema = _validate_table(table_name)
    if key_field not in schema["columns"]:
        return f"ERROR: '{key_field}' is not a valid column of '{table_name}'."
    data = _filter_columns(table_name, update_data)
    if not data:
        return "ERROR: update_data must contain at least one column."

    set_clause = ", ".join(f"{col} = ?" for col in data)
    sql = f"UPDATE {table_name} SET {set_clause} WHERE {key_field} = ?"

    conn = _connect()
    try:
        cursor = conn.execute(sql, [*data.values(), key_value])
        conn.commit()
        if cursor.rowcount == 0:
            return f"No row found in '{table_name}' where {key_field} = {key_value!r}."
        return f"OK: updated {cursor.rowcount} row(s) in '{table_name}'."
    finally:
        conn.close()


@mcp.tool()
def redact_pii_text(text: str) -> str:
    """Replace Social Security Numbers, phone numbers, and email addresses with [REDACTED PII].

    Args:
        text: Raw text to scrub before it may be released to a requester.
    """
    redacted = SSN_RE.sub("[REDACTED PII]", text)
    redacted = PHONE_RE.sub("[REDACTED PII]", redacted)
    redacted = EMAIL_RE.sub("[REDACTED PII]", redacted)
    return redacted


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    print(f"[records-db-mcp] using database at {DB_PATH}", file=sys.stderr)
    if transport != "stdio":
        print(f"[records-db-mcp] serving over {transport} at {MCP_HOST}:{MCP_PORT}", file=sys.stderr)
    mcp.run(transport=transport)
