"""
Safe Recovery — The Robust Algorithm.

Validates the full commit chain before exposing any record.
Any broken link in the chain → record is treated as uncommitted → rolled back.

Chain:  active metadata → data block → commit marker (must exist) → checksum (if present, must match)
"""
from engine.simulated_disk import SimulatedDisk
from engine.types import RecoveredRecord


def _compute_checksum_from_data(data_page: dict) -> str:
    """Recompute checksum from persisted data page fields."""
    raw = f"{data_page['key']}:{data_page['value']}:{data_page['version']}"
    h = 5381
    for ch in raw:
        h = ((h << 5) + h) ^ ord(ch)
    return f"crc32_{h & 0xFFFFFFFF:08x}"


def safe_recover(disk: SimulatedDisk) -> list[RecoveredRecord]:
    """
    Recover records by validating the full persistence chain.

    A record is exposed ONLY if ALL of the following are true:
      1. Metadata entry exists and active=True
      2. Data page exists for the referenced block
      3. Commit marker exists and committed=True  ← the key guard
      4. If a checksum is persisted, it must match the data

    Any missing link → record is NOT exposed (rolled back silently).
    """
    records = []

    for key, meta in disk.persisted["metadata_index"].items():
        if not meta.get("active"):
            continue

        txn_id = meta.get("txn_id")
        block_id = meta.get("block_id")

        if not txn_id or not block_id:
            continue

        data_page = disk.persisted["data_pages"].get(block_id)
        if not data_page:
            continue

        # ── GUARD 1: Commit marker must exist and be committed ────────────────
        commit = disk.persisted["commit_markers"].get(txn_id)
        if not commit or not commit.get("committed"):
            # No commit marker → uncommitted → skip (roll back)
            continue

        # ── GUARD 2: Checksum integrity (if checksum was persisted) ───────────
        stored_checksum = disk.persisted["checksums"].get(txn_id)
        if stored_checksum:
            actual_checksum = _compute_checksum_from_data(data_page)
            if stored_checksum != actual_checksum:
                # Checksum mismatch → data corrupted → skip
                continue

        # All guards passed → record is genuinely committed → expose it
        records.append(RecoveredRecord(
            key=key,
            value=data_page["value"],
            version=data_page["version"],
            txn_id=txn_id,
        ))

    return records
