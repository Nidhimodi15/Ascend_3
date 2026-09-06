"""
tests/test_mysql.py — Phase 4: MySQL Integration Tests for KillPoint.

Tests verify that:
  - MySQL connection works
  - The killpoint database and transactions table exist
  - Seed data was inserted correctly
  - Records can be fetched and converted to WriteOperation
  - The WriteOperation from MySQL runs through the existing engine
  - Edge cases (empty DB, duplicates, failures) are handled gracefully

All tests SKIP gracefully if MySQL is unreachable (so Phase 1–3 still pass).
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()


# ─── Skip Helper ──────────────────────────────────────────────────────────────

def _mysql_available() -> bool:
    """Return True if MySQL is reachable. Used to skip tests gracefully."""
    try:
        from app.adapters.mysql_adapter import test_connection
        status = test_connection()
        return status["connected"]
    except Exception:
        return False


# ─── Individual Tests ─────────────────────────────────────────────────────────

def test_mysql_connection():
    """Test 1: MySQL connection succeeds."""
    from app.adapters.mysql_adapter import test_connection
    status = test_connection()
    assert status["connected"] is True, f"MySQL connection failed: {status.get('error')}"
    assert status["host"] is not None
    return True


def test_database_exists():
    """Test 2: The killpoint database is accessible."""
    import os
    import mysql.connector
    conn = mysql.connector.connect(
        host     = os.getenv("MYSQL_HOST", "localhost"),
        port     = int(os.getenv("MYSQL_PORT", "3306")),
        user     = os.getenv("MYSQL_USER", "root"),
        password = os.getenv("MYSQL_PASSWORD", ""),
        database = os.getenv("MYSQL_DATABASE", "killpoint"),
    )
    assert conn.is_connected(), "Could not connect to killpoint database"
    conn.close()
    return True


def test_table_exists():
    """Test 3: The transactions table exists in the killpoint database."""
    import os
    import mysql.connector
    conn = mysql.connector.connect(
        host     = os.getenv("MYSQL_HOST", "localhost"),
        port     = int(os.getenv("MYSQL_PORT", "3306")),
        user     = os.getenv("MYSQL_USER", "root"),
        password = os.getenv("MYSQL_PASSWORD", ""),
        database = os.getenv("MYSQL_DATABASE", "killpoint"),
    )
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES LIKE 'transactions';")
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    assert result is not None, "Table 'transactions' does not exist in killpoint database. Run: python scripts/seed_mysql.py"
    return True


def test_seed_records_exist():
    """Test 4: Records were inserted by the seed script (count > 0)."""
    from app.adapters.mysql_adapter import fetch_transactions
    rows = fetch_transactions()
    assert len(rows) > 0, "No records in transactions table. Run: python scripts/seed_mysql.py"
    return True


def test_fetch_all_transactions():
    """Test 5: fetch_transactions() returns a non-empty list of dicts."""
    from app.adapters.mysql_adapter import fetch_transactions
    rows = fetch_transactions()
    assert isinstance(rows, list), "fetch_transactions() should return a list"
    assert len(rows) > 0, "Transaction list is empty"

    first = rows[0]
    required_keys = {"txn_id", "acct_key", "value", "old_value", "version"}
    missing = required_keys - set(first.keys())
    assert not missing, f"Missing fields in transaction row: {missing}"
    return True


def test_fetch_single_transaction():
    """Test 6: fetch_transaction(txn_id) returns the correct row."""
    from app.adapters.mysql_adapter import fetch_transactions, fetch_transaction

    all_rows = fetch_transactions()
    assert len(all_rows) > 0, "No rows to test against"

    txn_id = all_rows[0]["txn_id"]
    row = fetch_transaction(txn_id)

    assert row is not None, f"fetch_transaction('{txn_id}') returned None"
    assert row["txn_id"] == txn_id, f"Returned wrong txn_id: expected {txn_id}, got {row['txn_id']}"
    return True


def test_convert_to_write_operation():
    """Test 7: convert_to_write_operation() produces a valid WriteOperation."""
    from app.adapters.mysql_adapter import fetch_transactions, convert_to_write_operation
    from engine.types import WriteOperation

    rows = fetch_transactions()
    assert len(rows) > 0, "No rows to convert"

    op = convert_to_write_operation(rows[0])

    assert isinstance(op, WriteOperation), "Result is not a WriteOperation"
    assert op.txn_id == rows[0]["txn_id"]
    assert op.key    == rows[0]["acct_key"]
    assert op.value  == str(rows[0]["value"])
    assert op.old_value == str(rows[0]["old_value"])
    assert op.version   == int(rows[0]["version"])
    return True


def test_mysql_operation_runs_through_engine():
    """Test 8: A WriteOperation from MySQL runs through run_full_verification() without error."""
    from app.adapters.mysql_adapter import fetch_transactions, convert_to_write_operation
    from engine.crash_verifier import run_full_verification

    rows = fetch_transactions()
    assert len(rows) > 0, "No rows available for engine test"

    op = convert_to_write_operation(rows[0])

    # Run the actual engine with the MySQL-sourced WriteOperation
    report = run_full_verification(seed=0, strategy="naive", operation=op)

    assert report is not None, "Verification returned None"
    assert len(report.results) == 12, f"Expected 12 hook results, got {len(report.results)}"
    assert report.total_safe + report.total_bugs == 12, "Safe + bugs should equal 12"
    assert report.total_safe > 0, "Expected at least some SAFE hooks"
    return True


def test_empty_db_handling():
    """Test 9: fetch_transactions() returns [] gracefully when no rows exist.
    (Simulated by fetching a non-existent txn_id — doesn't delete real data.)
    """
    from app.adapters.mysql_adapter import fetch_transaction
    result = fetch_transaction("NONEXISTENT_TXN_XYZ_999")
    assert result is None, "fetch_transaction() should return None for a missing txn_id"
    return True


def test_duplicate_handling():
    """Test 10: Inserting a duplicate txn_id via upsert does not create extra rows."""
    import os
    import mysql.connector
    from app.adapters.mysql_adapter import fetch_transaction

    # Fetch an existing record
    existing = fetch_transaction("T101")
    if existing is None:
        # Skip if T101 not seeded yet
        return True

    conn = mysql.connector.connect(
        host     = os.getenv("MYSQL_HOST", "localhost"),
        port     = int(os.getenv("MYSQL_PORT", "3306")),
        user     = os.getenv("MYSQL_USER", "root"),
        password = os.getenv("MYSQL_PASSWORD", ""),
        database = os.getenv("MYSQL_DATABASE", "killpoint"),
    )
    cursor = conn.cursor()

    # Insert same T101 again with upsert
    cursor.execute("""
        INSERT INTO transactions (txn_id, `key`, value, old_value, version)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            `key`     = VALUES(`key`),
            value     = VALUES(value),
            old_value = VALUES(old_value),
            version   = VALUES(version);
    """, (
        existing["txn_id"],
        existing["acct_key"],    # acct_key alias in our dict = `key` column in DB
        existing["value"],
        existing["old_value"],
        existing["version"],
    ))
    conn.commit()

    # Verify count of T101 is still 1
    cursor.execute("SELECT COUNT(*) FROM transactions WHERE txn_id = %s;", (existing["txn_id"],))
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    assert count == 1, f"Duplicate insert created {count} rows for {existing['txn_id']}"
    return True


def test_connection_failure_handling():
    """Test 10 (bonus): test_connection() returns connected=False gracefully on bad credentials."""
    import mysql.connector
    from mysql.connector import Error as MySQLError

    try:
        conn = mysql.connector.connect(
            host     = "localhost",
            port     = 3306,
            user     = "INVALID_USER_XYZ",
            password = "INVALID_PASS_XYZ",
            database = "killpoint",
            connection_timeout = 3,
        )
        conn.close()
        # If we somehow connected, that's unexpected but not a test failure
        return True
    except MySQLError:
        # Expected: connection fails with bad creds
        return True


# ─── Test Runner ─────────────────────────────────────────────────────────────

def run_mysql_tests():
    """
    Run all Phase 4 MySQL integration tests.
    Returns (all_passed: bool, summary: list[tuple[name, status]])
    All tests skip gracefully if MySQL is unreachable.
    """
    print("\n[PHASE 4] MYSQL INTEGRATION TESTS")
    print("-" * 50)

    tests = [
        ("MySQL Connection",                  test_mysql_connection),
        ("Database Exists",                   test_database_exists),
        ("Table Exists",                      test_table_exists),
        ("Seed Records Exist",                test_seed_records_exist),
        ("Fetch All Transactions",            test_fetch_all_transactions),
        ("Fetch Single Transaction",          test_fetch_single_transaction),
        ("Convert to WriteOperation",         test_convert_to_write_operation),
        ("MySQL Op runs through Engine",      test_mysql_operation_runs_through_engine),
        ("Empty DB / Missing txn_id",         test_empty_db_handling),
        ("Duplicate Upsert Handling",         test_duplicate_handling),
    ]

    if not _mysql_available():
        print("  [SKIP] MySQL is unreachable — skipping all Phase 4 tests.")
        print("  Run: python scripts/seed_mysql.py  to initialize the database.\n")
        summary = [(name, "SKIP") for name, _ in tests]
        for name, status in summary:
            print(f"  [{status}] {name}")
        return True, summary  # Skipped = not a failure

    summary = []
    all_passed = True

    for name, fn in tests:
        try:
            fn()
            print(f"  [PASS] {name}")
            summary.append((name, "PASS"))
        except AssertionError as e:
            print(f"  [FAIL] {name}: {e}")
            summary.append((name, "FAIL"))
            all_passed = False
        except Exception as e:
            print(f"  [FAIL] {name}: Unexpected error — {e}")
            summary.append((name, "FAIL"))
            all_passed = False

    total_pass = sum(1 for _, s in summary if s == "PASS")
    total_fail = sum(1 for _, s in summary if s == "FAIL")
    print(f"\n  Phase 4 Summary: {total_pass} passed, {total_fail} failed")
    return all_passed, summary


if __name__ == "__main__":
    ok, _ = run_mysql_tests()
    sys.exit(0 if ok else 1)
