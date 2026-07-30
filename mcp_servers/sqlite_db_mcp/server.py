"""MCP stdio server exposing basic CRUD tools over data/social_services.db.

Table and column names are validated against a fixed schema whitelist before
being interpolated into SQL — only values are ever passed as bind parameters.
"""
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = REPO_ROOT / "data" / "social_services.db"

SCHEMA: dict[str, dict[str, Any]] = {
    "citizens": {
        "columns": ["nic", "full_name", "age", "monthly_income", "phone"],
        "primary_key": "nic",
    },
    "welfare_applications": {
        "columns": ["app_id", "nic", "benefit_type", "status", "notes", "created_at"],
        "primary_key": "app_id",
    },
}

SEED_CITIZENS = [
    ("851234567V", "Kamal Perera", 67, 8500.0, "0771234567"),
    ("923456789V", "Nimal Silva", 45, 22000.0, "0779876543"),
    ("601122334V", "Somawathie Fernando", 72, 6000.0, "0765554433"),
]

SEED_APPLICATIONS = [
    ("APP-0001", "851234567V", "senior_citizen_allowance", "approved", "Verified by GN certificate.", None),
    ("APP-0002", "601122334V", "medical_low_income_aid", "pending", "Awaiting PHI home visit report.", None),
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
            CREATE TABLE IF NOT EXISTS citizens (
                nic TEXT PRIMARY KEY,
                full_name TEXT,
                age INTEGER,
                monthly_income REAL,
                phone TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS welfare_applications (
                app_id TEXT PRIMARY KEY,
                nic TEXT,
                benefit_type TEXT,
                status TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (nic) REFERENCES citizens(nic)
            )
            """
        )

        if conn.execute("SELECT COUNT(*) FROM citizens").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO citizens (nic, full_name, age, monthly_income, phone) VALUES (?, ?, ?, ?, ?)",
                SEED_CITIZENS,
            )
        if conn.execute("SELECT COUNT(*) FROM welfare_applications").fetchone()[0] == 0:
            for app_id, nic, benefit_type, status, notes, created_at in SEED_APPLICATIONS:
                if created_at is None:
                    conn.execute(
                        "INSERT INTO welfare_applications (app_id, nic, benefit_type, status, notes) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (app_id, nic, benefit_type, status, notes),
                    )
                else:
                    conn.execute(
                        "INSERT INTO welfare_applications "
                        "(app_id, nic, benefit_type, status, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (app_id, nic, benefit_type, status, notes, created_at),
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

mcp = FastMCP("sqlite-db")


@mcp.tool()
def db_create_record(table_name: str, record_data: dict[str, Any]) -> str:
    """Insert a new row into 'citizens' or 'welfare_applications'.

    Args:
        table_name: 'citizens' or 'welfare_applications'.
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
    """Fetch rows from 'citizens' or 'welfare_applications' matching query_params.

    Args:
        table_name: 'citizens' or 'welfare_applications'.
        query_params: Column-value pairs to filter by (e.g. {"nic": "851234567V"}).
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
def db_update_record(table_name: str, key_field: str, key_value: str, update_data: dict[str, Any]) -> str:
    """Update an existing row in 'citizens' or 'welfare_applications'.

    Args:
        table_name: 'citizens' or 'welfare_applications'.
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
    """Delete a row from 'citizens' or 'welfare_applications'.

    Args:
        table_name: 'citizens' or 'welfare_applications'.
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
    print(f"[sqlite-db-mcp] using database at {DB_PATH}", file=sys.stderr)
    mcp.run(transport="stdio")
