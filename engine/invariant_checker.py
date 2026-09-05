"""
Invariant Checker — The Discovery Engine.

This module has ZERO hardcoded knowledge of which hooks pass or fail.
It receives the recovered state and disk snapshot AFTER recovery runs,
and independently evaluates 4 formal rules.

If the recovery algorithm has a flaw, the checker discovers it here.
The verifier simply orchestrates — this module is the sole arbiter of correctness.
"""
from engine.types import (
    RecoveredRecord,
    WriteOperation,
    DiskSnapshot,
    InvariantResult,
)


def _compute_checksum_from_record(record: RecoveredRecord) -> str:
    """Recompute checksum from a recovered record."""
    raw = f"{record.key}:{record.value}:{record.version}"
    h = 5381
    for ch in raw:
        h = ((h << 5) + h) ^ ord(ch)
    return f"crc32_{h & 0xFFFFFFFF:08x}"


def check_invariants(
    recovered_records: list[RecoveredRecord],
    operation: WriteOperation,
    disk_snapshot: DiskSnapshot,
    write_was_acknowledged: bool,
) -> list[InvariantResult]:
    """
    Evaluate 4 formal invariants against the recovered store state.

    Parameters:
      recovered_records       — what the recovery algorithm returned
      operation               — the original write that was in flight during the crash
      disk_snapshot           — snapshot of persisted disk BEFORE recovery ran
      write_was_acknowledged  — True if write completed (all 12 steps done) before crash

    Returns:
      List of InvariantResult objects — one per rule.
      Caller determines verdict based on whether any passed=False.

    This function does NOT decide SAFE/BUG. It only reports pass/fail per rule.
    """
    results: list[InvariantResult] = []

    # ─────────────────────────────────────────────────────────────────────────
    # INV-1: Valid Record Format
    # Every exposed record must have non-null, correctly structured fields.
    # ─────────────────────────────────────────────────────────────────────────
    format_ok = True
    bad_record_desc = ""
    for r in recovered_records:
        missing = []
        if not r.key:     missing.append("key")
        if not r.value:   missing.append("value")
        if not r.version: missing.append("version")
        if not r.txn_id:  missing.append("txn_id")
        if missing:
            format_ok = False
            bad_record_desc = f"Record key='{r.key}' missing fields: {', '.join(missing)}"
            break

    results.append(InvariantResult(
        invariant_id="INV-1",
        name="Valid Record Format",
        passed=format_ok,
        expected="All recovered records must have non-empty key, value, version, txn_id",
        actual="All fields present in all records" if format_ok else bad_record_desc,
        details=(
            f"Checked {len(recovered_records)} recovered record(s). All structurally valid."
            if format_ok else
            f"Structural corruption found in recovered record: {bad_record_desc}"
        ),
    ))

    # ─────────────────────────────────────────────────────────────────────────
    # INV-2: No Acknowledged Write Missing
    # If the write was acknowledged (all 12 steps completed), the record MUST
    # survive recovery. If crash happened mid-write, this invariant is N/A.
    # ─────────────────────────────────────────────────────────────────────────
    if write_was_acknowledged:
        record_found = any(r.key == operation.key for r in recovered_records)
        results.append(InvariantResult(
            invariant_id="INV-2",
            name="No Acknowledged Write Missing",
            passed=record_found,
            expected=f"Acknowledged key '{operation.key}' must be present in recovered store",
            actual=(
                f"Key '{operation.key}' successfully recovered"
                if record_found else
                f"Key '{operation.key}' is MISSING after recovery — acknowledged write LOST"
            ),
            details=(
                "Write was acknowledged (all 12 steps completed before crash). "
                + ("Record found — durability guarantee satisfied."
                   if record_found else
                   "Record missing — durability guarantee VIOLATED.")
            ),
        ))
    else:
        # Write crashed before completion — no durability guarantee was made
        results.append(InvariantResult(
            invariant_id="INV-2",
            name="No Acknowledged Write Missing",
            passed=True,
            expected="N/A — write was not acknowledged before crash",
            actual="N/A — no durability guarantee was made",
            details="Crash injected before write completion. INV-2 does not apply.",
        ))

    # ─────────────────────────────────────────────────────────────────────────
    # INV-3: No Uncommitted Value Exposed  ← The KEY invariant
    #
    # Rule: If no commit marker exists on persisted disk, recovery MUST NOT
    #       expose that transaction's records.
    #
    # The checker inspects the disk snapshot and the recovered records.
    # It does NOT know which hooks triggered this — it discovers it here.
    # ─────────────────────────────────────────────────────────────────────────
    commit_entry = disk_snapshot.commit_markers.get(operation.txn_id, {})
    has_commit_marker = bool(commit_entry.get("committed"))
    record_exposed = any(r.key == operation.key for r in recovered_records)

    if not has_commit_marker and record_exposed:
        # ❌ BUG DISCOVERED — uncommitted record is visible to readers
        wal_present   = len(disk_snapshot.wal) > 0
        data_present  = len(disk_snapshot.data_pages) > 0
        meta_present  = len(disk_snapshot.metadata_index) > 0
        csum_present  = operation.txn_id in disk_snapshot.checksums

        results.append(InvariantResult(
            invariant_id="INV-3",
            name="No Uncommitted Value Exposed",
            passed=False,
            expected=(
                f"Transaction '{operation.txn_id}' has no commit marker on disk — "
                f"key '{operation.key}' must NOT be visible after recovery"
            ),
            actual=(
                f"Key '{operation.key}' (value='{operation.value}') IS VISIBLE — "
                f"uncommitted record exposed to readers"
            ),
            details=(
                f"Transaction {operation.txn_id} lacks a commit marker on persisted disk, "
                f"yet recovery exposed the record. "
                f"Disk state at crash: "
                f"WAL={'present' if wal_present else 'empty'}, "
                f"Data={'present' if data_present else 'empty'}, "
                f"Metadata={'present' if meta_present else 'empty'}, "
                f"Checksum={'present' if csum_present else 'absent'}, "
                f"CommitMarker=absent. "
                f"Recovery violated atomicity: partial transaction is visible."
            ),
        ))

    elif has_commit_marker and record_exposed:
        results.append(InvariantResult(
            invariant_id="INV-3",
            name="No Uncommitted Value Exposed",
            passed=True,
            expected="Committed record may be visible",
            actual=f"Key '{operation.key}' is visible and commit marker is present — correct",
            details="Record is exposed AND commit marker is on persisted disk. Fully consistent.",
        ))

    else:
        # Record not exposed at all — safe regardless of commit state
        results.append(InvariantResult(
            invariant_id="INV-3",
            name="No Uncommitted Value Exposed",
            passed=True,
            expected="No uncommitted record exposed",
            actual="Recovery returned no records for this transaction",
            details=(
                "Recovery correctly did not expose this transaction. "
                f"CommitMarker={'present' if has_commit_marker else 'absent'}. "
                "No exposure → no violation."
            ),
        ))

    # ─────────────────────────────────────────────────────────────────────────
    # INV-4: Checksum Integrity
    # For every exposed record that has a persisted checksum, verify
    # checksum(recovered_data) == stored_checksum.
    # ─────────────────────────────────────────────────────────────────────────
    checksum_ok = True
    checksum_detail = ""
    for record in recovered_records:
        stored = disk_snapshot.checksums.get(record.txn_id)
        if stored:
            actual_csum = _compute_checksum_from_record(record)
            if stored != actual_csum:
                checksum_ok = False
                checksum_detail = (
                    f"Txn {record.txn_id}: stored={stored}, computed={actual_csum}"
                )
                break

    results.append(InvariantResult(
        invariant_id="INV-4",
        name="Checksum Integrity",
        passed=checksum_ok,
        expected="For every exposed record with a persisted checksum: checksum(data) == stored",
        actual=(
            "All checksums valid (or no checksums to verify)"
            if checksum_ok else
            f"Checksum MISMATCH detected — {checksum_detail}"
        ),
        details=(
            f"Verified checksums for {len(recovered_records)} recovered record(s). All match."
            if checksum_ok else
            f"Data corruption detected via checksum comparison: {checksum_detail}"
        ),
    ))

    return results
