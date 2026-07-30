"""MCP stdio server simulating a municipal online tax payment gateway.

Writes to the same data/tax_revenue.db used by mcp_servers/tax_db_mcp/server.py.
This is a SIMULATION only — no real bank or payment processor is contacted;
`create_payment_link` and `verify_and_settle_payment` fabricate transaction and
receipt identifiers locally.
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = REPO_ROOT / "data" / "tax_revenue.db"
CHECKOUT_BASE_URL = "http://localhost:8004/pay/checkout"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables if this process starts before tax_db_mcp has run."""
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
    conn.commit()


def _next_txn_id(conn: sqlite3.Connection) -> str:
    count = conn.execute("SELECT COUNT(*) FROM tax_payments WHERE transaction_id IS NOT NULL").fetchone()[0]
    return f"TXN-TAX-{9900 + count + 1}"


def _next_receipt_no(conn: sqlite3.Connection, year: int) -> str:
    count = conn.execute("SELECT COUNT(*) FROM tax_payments WHERE payment_status = 'PAID'").fetchone()[0]
    return f"RCT-{year}-{8800 + count + 1}"


mcp = FastMCP("payment-gateway")


@mcp.tool()
def create_payment_link(assessment_no: str, quarter: str, amount_lkr: float) -> str:
    """Generate a mock municipal payment gateway checkout link for a tax quarter.

    Creates or updates the corresponding row in `tax_payments` with status
    'PENDING_GATEWAY' and a fresh transaction ID. SIMULATION ONLY — no real
    payment processor is contacted.

    Args:
        assessment_no: The property's assessment number.
        quarter: Quarter being paid, e.g. 'Q1'.
        amount_lkr: Final amount in LKR to collect (with any discount or
            surcharge already applied by the caller).
    """
    conn = _connect()
    try:
        _ensure_schema(conn)
        year = datetime.now().year
        txn_id = _next_txn_id(conn)
        checkout_url = f"{CHECKOUT_BASE_URL}?txn_id={txn_id}"

        existing = conn.execute(
            "SELECT receipt_no FROM tax_payments WHERE assessment_no = ? AND quarter = ? AND year = ?",
            (assessment_no, quarter, year),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE tax_payments SET amount_paid = ?, payment_status = 'PENDING_GATEWAY', "
                "transaction_id = ?, updated_at = CURRENT_TIMESTAMP WHERE receipt_no = ?",
                (amount_lkr, txn_id, existing["receipt_no"]),
            )
        else:
            conn.execute(
                "INSERT INTO tax_payments "
                "(receipt_no, assessment_no, year, quarter, amount_paid, payment_status, transaction_id) "
                "VALUES (?, ?, ?, ?, ?, 'PENDING_GATEWAY', ?)",
                (f"PEND-{txn_id}", assessment_no, year, quarter, amount_lkr, txn_id),
            )
        conn.commit()

        return (
            f"Payment link created for assessment {assessment_no} ({quarter} {year}), "
            f"amount LKR {amount_lkr:,.2f}.\n"
            f"Checkout URL: {checkout_url}\n"
            f"Transaction ID: {txn_id}\n"
            f"Status: PENDING_GATEWAY (awaiting settlement)."
        )
    finally:
        conn.close()


@mcp.tool()
def verify_and_settle_payment(transaction_id: str) -> str:
    """Simulate bank settlement of a pending payment and issue a digital receipt.

    Marks the matching `tax_payments` row PAID and generates a receipt number.
    SIMULATION ONLY — no real bank settlement occurs.

    Args:
        transaction_id: The transaction ID returned by create_payment_link.
    """
    conn = _connect()
    try:
        _ensure_schema(conn)
        row = conn.execute(
            "SELECT * FROM tax_payments WHERE transaction_id = ?", (transaction_id,)
        ).fetchone()

        if row is None:
            return f"ERROR: no payment found for transaction_id '{transaction_id}'."
        if row["payment_status"] == "PAID":
            return f"Transaction {transaction_id} was already settled. Receipt: {row['receipt_no']}."

        receipt_no = _next_receipt_no(conn, row["year"])
        conn.execute(
            "UPDATE tax_payments SET receipt_no = ?, payment_status = 'PAID', "
            "updated_at = CURRENT_TIMESTAMP WHERE transaction_id = ?",
            (receipt_no, transaction_id),
        )
        conn.commit()

        settled_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        return (
            "=== MUNICIPAL TAX PAYMENT RECEIPT (SIMULATED) ===\n"
            f"Receipt No.     : {receipt_no}\n"
            f"Assessment No.  : {row['assessment_no']}\n"
            f"Period          : {row['quarter']} {row['year']}\n"
            f"Amount Paid     : LKR {row['amount_paid']:,.2f}\n"
            f"Transaction ID  : {transaction_id}\n"
            f"Settled At      : {settled_at}\n"
            "Status          : PAID\n"
            "=================================================="
        )
    finally:
        conn.close()


if __name__ == "__main__":
    print(f"[payment-mcp] using database at {DB_PATH}", file=sys.stderr)
    mcp.run(transport="stdio")
