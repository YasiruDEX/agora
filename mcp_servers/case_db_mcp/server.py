"""MCP stdio server exposing basic CRUD tools over data/case_management.db.

Table and column names are validated against a fixed schema whitelist before
being interpolated into SQL — only values are ever passed as bind parameters.

NOTE ON ACCESS CONTROL: this server has no notion of "who is asking" — it is a
generic data-access capability. On-Behalf-Of (caseworker) scoping is enforced
one layer up, in agents/case_management_agent/graph.py, which wraps these raw
tools so the agent's LLM can only ever reach case data through
ownership-checked wrappers (get_my_cases / get_case_notes / add_case_note /
update_case_status) rather than these unrestricted CRUD primitives.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_db_path() -> Path:
    """Configurable via CASE_DB_PATH so this server also works bundled
    standalone alongside a single agent, without the rest of the monorepo."""
    raw_path = os.environ.get("CASE_DB_PATH", str(REPO_ROOT / "data" / "case_management.db"))
    path = Path(raw_path)
    return path if path.is_absolute() else (REPO_ROOT / path)


DB_PATH = _resolve_db_path()

SCHEMA: dict[str, dict[str, Any]] = {
    "cases": {
        "columns": ["case_id", "citizen_nic", "citizen_name", "assigned_caseworker", "case_type", "status", "created_at"],
        "primary_key": "case_id",
    },
    "case_notes": {
        "columns": ["note_id", "case_id", "author_id", "note_text", "created_at"],
        "primary_key": "note_id",
    },
}

SEED_CASES = [
    ("CASE-2026-001", "DL-H84556712", "Linda Foster", "joan.ellis", "BENEFITS_REVIEW", "OPEN"),
    ("CASE-2026-002", "DL-E23456789", "Robert Martinez", "marcus.lee", "MEDICAL_AID_ASSESSMENT", "PENDING_REVIEW"),
]

SEED_NOTES = [
    ("NOTE-2026-001-1", "CASE-2026-001", "joan.ellis", "Initial intake complete. Awaiting income verification."),
    ("NOTE-2026-002-1", "CASE-2026-002", "marcus.lee", "Medical report received."),
]


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
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                citizen_nic TEXT,
                citizen_name TEXT,
                assigned_caseworker TEXT,
                case_type TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS case_notes (
                note_id TEXT PRIMARY KEY,
                case_id TEXT,
                author_id TEXT,
                note_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES cases(case_id)
            )
            """
        )

        if conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO cases (case_id, citizen_nic, citizen_name, assigned_caseworker, case_type, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                SEED_CASES,
            )
        if conn.execute("SELECT COUNT(*) FROM case_notes").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO case_notes (note_id, case_id, author_id, note_text) VALUES (?, ?, ?, ?)",
                SEED_NOTES,
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
MCP_PORT = int(os.environ.get("MCP_PORT", "9003"))

mcp = FastMCP("case-db", host=MCP_HOST, port=MCP_PORT)


@mcp.tool()
def db_read_record(table_name: str, query_params: dict[str, Any]) -> str:
    """Fetch rows from 'cases' or 'case_notes' matching query_params.

    Args:
        table_name: 'cases' or 'case_notes'.
        query_params: Column-value pairs to filter by (e.g. {"case_id": "CASE-2026-001"}
            or {"assigned_caseworker": "joan.ellis"}). Pass an empty dict to fetch all
            rows (capped at 50).
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
    """Insert a new row into 'cases' or 'case_notes'.

    Args:
        table_name: 'cases' or 'case_notes'.
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
    """Update an existing row in 'cases' or 'case_notes'.

    Args:
        table_name: 'cases' or 'case_notes'.
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


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    print(f"[case-db-mcp] using database at {DB_PATH}", file=sys.stderr)
    if transport != "stdio":
        print(f"[case-db-mcp] serving over {transport} at {MCP_HOST}:{MCP_PORT}", file=sys.stderr)
    mcp.run(transport=transport)
