"""
app/adapters/mysql_adapter.py — MySQL Data Adapter for KillPoint.

This adapter is the SOLE runtime source of transaction data.
It fetches actual stored records from the MySQL `killpoint` database
and converts them directly into the existing WriteOperation format
that the KillPoint verification engine expects.

SeededRandom is NOT used here. The actual field values (txn_id, acct_key,
value, old_value, version) are read directly from the MySQL `transactions`
table and mapped 1-to-1 into WriteOperation fields.
"""

import os
from dotenv import load_dotenv

load_dotenv()

MYSQL_HOST     = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT     = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER     = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "killpoint")


def _get_connection():
    """Create and return a MySQL connection using .env credentials."""
    import mysql.connector
    return mysql.connector.connect(
        host     = MYSQL_HOST,
        port     = MYSQL_PORT,
        user     = MYSQL_USER,
        password = MYSQL_PASSWORD,
        database = MYSQL_DATABASE,
        connection_timeout = 5,
    )


def test_connection() -> dict:
    """
    Test MySQL connectivity and return status details.
    Returns a dict with: connected (bool), host, database, error (str|None).
    Never raises — always returns a safe dict for API/UI consumption.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM transactions;")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return {
            "connected"  : True,
            "host"       : f"{MYSQL_HOST}:{MYSQL_PORT}",
            "database"   : MYSQL_DATABASE,
            "table"      : "transactions",
            "row_count"  : count,
            "error"      : None,
        }
    except Exception as e:
        return {
            "connected"  : False,
            "host"       : f"{MYSQL_HOST}:{MYSQL_PORT}",
            "database"   : MYSQL_DATABASE,
            "table"      : "transactions",
            "row_count"  : 0,
            "error"      : str(e),
        }


def fetch_transactions() -> list:
    """
    Fetch all transaction records from MySQL.
    Returns a list of dicts, each representing one row.
    Returns [] if MySQL is unreachable or the table is empty.

    Each dict has keys: txn_id, acct_key, value, old_value, version.
    """
    try:
        conn   = _get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT txn_id, `key` AS acct_key, value, old_value, version "
            "FROM transactions ORDER BY txn_id;"
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception:
        return []


def fetch_transaction(txn_id: str) -> dict | None:
    """
    Fetch a single transaction by txn_id from MySQL.
    Returns the row as a dict, or None if not found or DB is unreachable.

    The returned dict has keys: txn_id, acct_key, value, old_value, version.
    """
    try:
        conn   = _get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT txn_id, `key` AS acct_key, value, old_value, version "
            "FROM transactions WHERE txn_id = %s LIMIT 1;",
            (txn_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row  # None if not found
    except Exception:
        return None


def convert_to_write_operation(row: dict):
    """
    Convert a MySQL transaction row directly into an engine WriteOperation.

    Mapping (MySQL column → WriteOperation field):
        txn_id    → txn_id
        acct_key  → key
        value     → value
        old_value → old_value
        version   → version

    NO SeededRandom is used here. The actual stored values from MySQL
    are passed directly into the existing WriteOperation dataclass.
    The KillPoint engine then operates on these real database values.
    """
    from engine.types import WriteOperation
    return WriteOperation(
        txn_id    = row["txn_id"],
        key       = row["acct_key"],
        value     = str(row["value"]),
        old_value = str(row["old_value"]),
        version   = int(row["version"]),
    )
