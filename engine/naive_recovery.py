"""
Naive Recovery — The Flawed Algorithm.

This algorithm has a genuine design flaw: it determines record validity
by checking data + metadata presence WITHOUT verifying the commit marker.

It has no idea this will cause problems — it's a common shortcut that
real systems have shipped with. Whether it causes a problem at any
specific crash point is discovered ONLY by the invariant checker.
"""
from engine.simulated_disk import SimulatedDisk
from engine.types import RecoveredRecord


def naive_recover(disk: SimulatedDisk) -> list[RecoveredRecord]:
    """
    Recover records by scanning metadata index and data pages.

    Algorithm:
      For each metadata entry that is marked active:
        Look up the data page it points to.
        If data page exists → record is considered valid and exposed.

    This algorithm does NOT check:
      - Commit markers
      - Checksums
      - WAL consistency

    Whether this causes a correctness violation depends on the crash point.
    The invariant checker will discover if the result is correct.
    """
    records = []

    for key, meta in disk.persisted["metadata_index"].items():
        # Only consider entries that have active=True
        if not meta.get("active"):
            continue

        block_id = meta.get("block_id")
        if not block_id:
            continue

        data_page = disk.persisted["data_pages"].get(block_id)
        if not data_page:
            continue

        # Naive check: data + active metadata → assume committed ← THE FLAW
        records.append(RecoveredRecord(
            key=key,
            value=data_page["value"],
            version=data_page["version"],
            txn_id=data_page["txn_id"],
        ))

    return records
