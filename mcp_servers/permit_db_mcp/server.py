"""MCP stdio server exposing basic CRUD tools over a permit-tracking SQLite DB.

Table and column names are validated against a fixed schema whitelist before
being interpolated into SQL — only values are ever passed as bind parameters.

The database file is configurable via PERMIT_DB_PATH so the same codebase can
run as multiple independent instances (e.g. a Building Permits instance and a
Business Licenses instance), each backed by its own isolated SQLite file with
no shared state or locking between them. PERMIT_CATEGORY, if set, additionally
selects which category of seed data a *newly created* database is populated
with.
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
    raw_path = os.environ.get("PERMIT_DB_PATH", "data/permits.db")
    path = Path(raw_path)
    return path if path.is_absolute() else (REPO_ROOT / path)


DB_PATH = _resolve_db_path()
PERMIT_CATEGORY = os.environ.get("PERMIT_CATEGORY")

SCHEMA: dict[str, dict[str, Any]] = {
    "applicants": {
        "columns": ["nic", "full_name", "phone", "address"],
        "primary_key": "nic",
    },
    "permit_applications": {
        "columns": [
            "app_id",
            "nic",
            "permit_type",
            "property_address",
            "sq_ft",
            "status",
            "inspection_date",
            "created_at",
        ],
        "primary_key": "app_id",
    },
}

# Seed data is keyed by PERMIT_CATEGORY so each dedicated instance (Building
# Permits, Business Licenses, ...) gets a freshly-created database populated
# only with records relevant to its own category. A database with no
# PERMIT_CATEGORY set (the original single-instance mode) falls back to the
# mixed "DEFAULT" seed covering all three permit types.
SEED_BY_CATEGORY: dict[str, dict[str, list[tuple]]] = {
    "BUILDING_PLAN": {
        "applicants": [
            ("198204100V", "Ariyawansa Gunasekera", "0771112233", "No. 23, Station Road, Maharagama"),
            ("851234567V", "Kamal Perera", "0771234567", "No. 12, Temple Road, Nugegoda"),
        ],
        "applications": [
            ("APP-BP-5001", "198204100V", "BUILDING_PLAN", "No. 23, Station Road, Maharagama", 2200.0, "INSPECTION_SCHEDULED", "2026-08-18", None),
            ("APP-BP-1001", "851234567V", "BUILDING_PLAN", "No. 12, Temple Road, Nugegoda", 1850.0, "INSPECTION_SCHEDULED", "2026-08-12", None),
            ("APP-SL-2001", "851234567V", "STREET_LINE", "No. 12, Temple Road, Nugegoda", None, "DOCUMENTS_PENDING", None, None),
        ],
    },
    "TRADE_LICENSE": {
        "applicants": [
            ("199012300V", "Chathurika Wickramasinghe", "0774445566", "No. 88, Main Street, Kandy"),
            ("770099887V", "Ruwan Jayasuriya", "0712223344", "No. 7, Lake Drive, Colombo 08"),
        ],
        "applications": [
            ("APP-TL-6001", "199012300V", "TRADE_LICENSE", "No. 88, Main Street, Kandy", 450.0, "DOCUMENTS_PENDING", None, None),
            ("APP-TL-3001", "770099887V", "TRADE_LICENSE", "No. 7, Lake Drive, Colombo 08", 620.0, "APPROVED", None, None),
        ],
    },
    "DEFAULT": {
        "applicants": [
            ("851234567V", "Kamal Perera", "0771234567", "No. 12, Temple Road, Nugegoda"),
            ("923456789V", "Nimal Silva", "0779876543", "No. 45, Galle Road, Dehiwala"),
            ("770099887V", "Ruwan Jayasuriya", "0712223344", "No. 7, Lake Drive, Colombo 08"),
        ],
        "applications": [
            ("APP-BP-1001", "851234567V", "BUILDING_PLAN", "No. 12, Temple Road, Nugegoda", 1850.0, "INSPECTION_SCHEDULED", "2026-08-12", None),
            ("APP-SL-2001", "923456789V", "STREET_LINE", "No. 45, Galle Road, Dehiwala", None, "DOCUMENTS_PENDING", None, None),
            ("APP-TL-3001", "770099887V", "TRADE_LICENSE", "No. 7, Lake Drive, Colombo 08", 620.0, "APPROVED", None, None),
        ],
    },
}


def _active_seed() -> dict[str, list[tuple]]:
    return SEED_BY_CATEGORY.get(PERMIT_CATEGORY, SEED_BY_CATEGORY["DEFAULT"])


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
            CREATE TABLE IF NOT EXISTS applicants (
                nic TEXT PRIMARY KEY,
                full_name TEXT,
                phone TEXT,
                address TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS permit_applications (
                app_id TEXT PRIMARY KEY,
                nic TEXT,
                permit_type TEXT,
                property_address TEXT,
                sq_ft REAL,
                status TEXT,
                inspection_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (nic) REFERENCES applicants(nic)
            )
            """
        )

        seed = _active_seed()

        if conn.execute("SELECT COUNT(*) FROM applicants").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO applicants (nic, full_name, phone, address) VALUES (?, ?, ?, ?)",
                seed["applicants"],
            )
        if conn.execute("SELECT COUNT(*) FROM permit_applications").fetchone()[0] == 0:
            for app_id, nic, permit_type, property_address, sq_ft, status, inspection_date, created_at in seed["applications"]:
                if created_at is None:
                    conn.execute(
                        "INSERT INTO permit_applications "
                        "(app_id, nic, permit_type, property_address, sq_ft, status, inspection_date) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (app_id, nic, permit_type, property_address, sq_ft, status, inspection_date),
                    )
                else:
                    conn.execute(
                        "INSERT INTO permit_applications "
                        "(app_id, nic, permit_type, property_address, sq_ft, status, inspection_date, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (app_id, nic, permit_type, property_address, sq_ft, status, inspection_date, created_at),
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
# When running two instances of this codebase (Building Permits / Business
# Licenses), set MCP_PORT distinctly per instance alongside PERMIT_DB_PATH.
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "9004"))

mcp = FastMCP("permit-db", host=MCP_HOST, port=MCP_PORT)


@mcp.tool()
def db_create_record(table_name: str, record_data: dict[str, Any]) -> str:
    """Insert a new row into 'applicants' or 'permit_applications'.

    Args:
        table_name: 'applicants' or 'permit_applications'.
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
def db_read_record(table_name: str, query_params: dict[str, Any]) -> str:
    """Fetch rows from 'applicants' or 'permit_applications' matching query_params.

    Args:
        table_name: 'applicants' or 'permit_applications'.
        query_params: Column-value pairs to filter by (e.g. {"nic": "851234567V"}
            or {"app_id": "APP-BP-1001"}). Pass an empty dict to fetch all rows
            (capped at 50).
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
def db_update_record(table_name: str, key_field: str, key_value: str, update_data: dict[str, Any]) -> str:
    """Update an existing row in 'applicants' or 'permit_applications'.

    Args:
        table_name: 'applicants' or 'permit_applications'.
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
def db_delete_record(table_name: str, key_field: str, key_value: str) -> str:
    """Delete a row from 'applicants' or 'permit_applications'.

    Args:
        table_name: 'applicants' or 'permit_applications'.
        key_field: Column used to identify the row (typically the primary key).
        key_value: Value of key_field identifying the row to delete.
    """
    schema = _validate_table(table_name)
    if key_field not in schema["columns"]:
        return f"ERROR: '{key_field}' is not a valid column of '{table_name}'."

    sql = f"DELETE FROM {table_name} WHERE {key_field} = ?"
    conn = _connect()
    try:
        cursor = conn.execute(sql, [key_value])
        conn.commit()
        if cursor.rowcount == 0:
            return f"No row found in '{table_name}' where {key_field} = {key_value!r}."
        return f"OK: deleted {cursor.rowcount} row(s) from '{table_name}'."
    finally:
        conn.close()


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    print(f"[permit-db-mcp] using database at {DB_PATH}", file=sys.stderr)
    if transport != "stdio":
        print(f"[permit-db-mcp] serving over {transport} at {MCP_HOST}:{MCP_PORT}", file=sys.stderr)
    mcp.run(transport=transport)
