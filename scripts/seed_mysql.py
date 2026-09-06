"""
scripts/seed_mysql.py — ONE-TIME MySQL Database Initializer for KillPoint.

Usage:
    python scripts/seed_mysql.py

What it does:
  1. Connects to the local MySQL `killpoint` database using .env credentials.
  2. Creates the `transactions` table if it does not already exist.
  3. Uses SeededRandom (seed=12345) to generate deterministic transaction values.
  4. INSERTs the actual field values into MySQL (upsert — safe against duplicates).
  5. Prints a formatted summary of what was inserted.

IMPORTANT:
  - SeededRandom is used ONLY HERE, during one-time initialization.
  - At runtime the application reads actual stored values from MySQL.
  - Running this script multiple times is safe (ON DUPLICATE KEY UPDATE).
"""

import sys
import os

# Add project root to path so we can import engine modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

import mysql.connector
from mysql.connector import Error as MySQLError

from engine.seeded_random import SeededRandom


# ─── Configuration ─────────────────────────────────────────────────────────────

SEED           = 12345
NUM_RECORDS    = 10
MYSQL_HOST     = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT     = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER     = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "killpoint")


# ─── Table DDL ────────────────────────────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id        INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    txn_id    VARCHAR(50)  NOT NULL UNIQUE,
    `key`     VARCHAR(100) NOT NULL,
    value     VARCHAR(255) NOT NULL,
    version   INT          DEFAULT 1,
    old_value VARCHAR(255) DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

UPSERT_SQL = """
INSERT INTO transactions (txn_id, `key`, value, old_value, version)
VALUES (%s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    `key`     = VALUES(`key`),
    value     = VALUES(value),
    old_value = VALUES(old_value),
    version   = VALUES(version);
"""


# ─── Transaction Generation ────────────────────────────────────────────────────

def generate_transactions(seed: int, count: int) -> list:
    """
    Generate deterministic transaction records using SeededRandom.
    The SAME seed ALWAYS produces the SAME records.
    Values are generated once and then stored in MySQL as real data.
    SeededRandom is NEVER called at application runtime.
    """
    records = []
    rng = SeededRandom(seed)

    for i in range(count):
        txn_num  = 100 + i + 1                      # T101, T102, ..., T110
        key_sfx  = rng.next_int(1, 100)             # account suffix
        value    = rng.next_int(100, 99999)          # transaction amount
        old_val  = rng.next_int(100, 99999)          # previous balance
        version  = rng.next_int(1, 50)              # record version

        records.append({
            "txn_id"   : f"T{txn_num}",
            "key"      : f"account_{key_sfx:03d}",
            "value"    : str(value),
            "old_value": str(old_val),
            "version"  : version,
        })

    return records


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  KILLPOINT — MYSQL SEED INITIALIZATION")
    print("=" * 55)
    print(f"\n  Seed         : {SEED}")
    print(f"  Records      : {NUM_RECORDS}")
    print(f"  Host         : {MYSQL_HOST}:{MYSQL_PORT}")
    print(f"  Database     : {MYSQL_DATABASE}")
    print()

    # Step 1: Generate deterministic records (SeededRandom — one-time only)
    records = generate_transactions(SEED, NUM_RECORDS)

    # Step 2: Connect to MySQL
    try:
        conn = mysql.connector.connect(
            host     = MYSQL_HOST,
            port     = MYSQL_PORT,
            user     = MYSQL_USER,
            password = MYSQL_PASSWORD,
            database = MYSQL_DATABASE,
        )
        print("  MySQL        : Connected OK")
    except MySQLError as e:
        print(f"\n  [ERROR] Cannot connect to MySQL: {e}")
        print(f"\n  Make sure MySQL is running and the `{MYSQL_DATABASE}` database exists.")
        print(f"  Create it with:  CREATE DATABASE {MYSQL_DATABASE};")
        sys.exit(1)

    cursor = conn.cursor()

    # Step 3: Create table if needed
    cursor.execute(CREATE_TABLE_SQL)
    conn.commit()
    print("  Table        : transactions OK")
    print()

    # Step 4: Upsert records (INSERT ... ON DUPLICATE KEY UPDATE)
    inserted = []
    for row in records:
        cursor.execute(UPSERT_SQL, (
            row["txn_id"],
            row["key"],
            row["value"],
            row["old_value"],
            row["version"],
        ))
        inserted.append(row)

    conn.commit()

    # Step 5: Print formatted summary
    print("  Inserted / Updated:")
    print("  " + "-" * 53)
    print(f"  {'TXN ID':<8} {'ACCOUNT':<15} {'VALUE':>8} {'OLD VALUE':>10} {'VER':>4}")
    print("  " + "-" * 53)
    for row in inserted:
        print(
            f"  {row['txn_id']:<8} "
            f"{row['key']:<15} "
            f"{row['value']:>8} "
            f"{row['old_value']:>10} "
            f"{row['version']:>4}"
        )
    print("  " + "-" * 53)

    # Step 6: Verify count in DB
    cursor.execute("SELECT COUNT(*) FROM transactions;")
    total = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    print()
    print(f"  Database     : {MYSQL_DATABASE}")
    print(f"  Total Rows   : {total}")
    print()
    print("=" * 55)
    print("  STATUS       : SUCCESS")
    print("=" * 55)
    print()
    print("  KillPoint will now read transactions from MySQL.")
    print("  Start the server:  python run.py")
    print()


if __name__ == "__main__":
    main()
