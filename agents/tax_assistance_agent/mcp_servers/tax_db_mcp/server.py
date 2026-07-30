"""MCP stdio server exposing basic CRUD tools over data/tax_revenue.db.

Table and column names are validated against a fixed schema whitelist before
being interpolated into SQL — only values are ever passed as bind parameters.

This database is shared with mcp_servers/payment_mcp/server.py, which writes
to the `tax_payments` table as part of the simulated payment gateway flow.
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
    """Configurable via TAX_DB_PATH so this server also works bundled
    standalone alongside a single agent, without the rest of the monorepo.
    mcp_servers/payment_mcp/server.py reads the same env var so both stay
    pointed at the same file."""
    raw_path = os.environ.get("TAX_DB_PATH", str(REPO_ROOT / "data" / "tax_revenue.db"))
    path = Path(raw_path)
    return path if path.is_absolute() else (REPO_ROOT / path)


DB_PATH = _resolve_db_path()

SCHEMA: dict[str, dict[str, Any]] = {
    "properties": {
        "columns": ["assessment_no", "nic", "owner_name", "property_address", "annual_value", "quarterly_rate"],
        "primary_key": "assessment_no",
    },
    "tax_payments": {
        "columns": [
            "receipt_no",
            "assessment_no",
            "year",
            "quarter",
            "amount_paid",
            "payment_status",
            "transaction_id",
            "updated_at",
        ],
        "primary_key": "receipt_no",
    },
}

SEED_PROPERTIES = [
    ("PROP-COL-2026-88", "197508100V", "K. L. Perera", "No. 55, Ward Place, Colombo 07", 250000.0, 12500.0),
]

SEED_TAX_PAYMENTS = [
    ("PEND-PROP-COL-2026-88-2026Q1", "PROP-COL-2026-88", 2026, "Q1", 0.0, "UNPAID", None),
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
            CREATE TABLE IF NOT EXISTS properties (
                assessment_no TEXT PRIMARY KEY,
                nic TEXT,
                owner_name TEXT,
                property_address TEXT,
                annual_value REAL,
                quarterly_rate REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tax_payments (
                receipt_no TEXT PRIMARY KEY,
                assessment_no TEXT,
                year INTEGER,
                quarter TEXT,
                amount_paid REAL,
                payment_status TEXT,
                transaction_id TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assessment_no) REFERENCES properties(assessment_no)
            )
            """
        )

        if conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO properties "
                "(assessment_no, nic, owner_name, property_address, annual_value, quarterly_rate) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                SEED_PROPERTIES,
            )
        if conn.execute("SELECT COUNT(*) FROM tax_payments").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO tax_payments "
                "(receipt_no, assessment_no, year, quarter, amount_paid, payment_status, transaction_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                SEED_TAX_PAYMENTS,
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

mcp = FastMCP("tax-db")


@mcp.tool()
def db_create_record(table_name: str, record_data: dict[str, Any]) -> str:
    """Insert a new row into 'properties' or 'tax_payments'.

    Args:
        table_name: 'properties' or 'tax_payments'.
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
    """Fetch rows from 'properties' or 'tax_payments' matching query_params.

    Args:
        table_name: 'properties' or 'tax_payments'.
        query_params: Column-value pairs to filter by (e.g. {"assessment_no": "PROP-COL-2026-88"}
            or {"nic": "197508100V"}). Pass an empty dict to fetch all rows (capped at 50).
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
    """Update an existing row in 'properties' or 'tax_payments'.

    Args:
        table_name: 'properties' or 'tax_payments'.
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
    """Delete a row from 'properties' or 'tax_payments'.

    Args:
        table_name: 'properties' or 'tax_payments'.
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
    print(f"[tax-db-mcp] using database at {DB_PATH}", file=sys.stderr)
    mcp.run(transport="stdio")
