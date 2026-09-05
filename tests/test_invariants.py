"""
test_invariants.py — Invariant Checker Test Suite.

Directly tests invariant_checker.py against controlled inputs:
  - INV-1: Valid Record Format (structural completeness)
  - INV-2: No Acknowledged Write Missing (durability guarantee)
  - INV-3: No Uncommitted Partial Value Exposed (atomicity guarantee)
  - INV-4: Checksum Integrity (data corruption detection)
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.simulated_disk import SimulatedDisk
from engine.types import RecoveredRecord, WriteOperation
from engine.invariant_checker import check_invariants, _compute_checksum_from_record
from engine.naive_recovery import naive_recover
from engine.safe_recovery import safe_recover


def test_inv_1_valid_record_format():
    """Test INV-1: Valid Record Format."""
    op = WriteOperation(txn_id="txn_101", key="acct_1", value="100", version=1, old_value="")
    disk = SimulatedDisk()
    snapshot = disk.snapshot()

    # 1. Valid record format -> PASS
    good_record = RecoveredRecord(key="acct_1", value="100", version=1, txn_id="txn_101")
    results = check_invariants([good_record], op, snapshot, write_was_acknowledged=False)
    inv1 = next(i for i in results if i.invariant_id == "INV-1")
    assert inv1.passed is True

    # 2. Invalid record format (missing key) -> FAIL
    bad_record = RecoveredRecord(key="", value="100", version=1, txn_id="txn_101")
    results_bad = check_invariants([bad_record], op, snapshot, write_was_acknowledged=False)
    inv1_bad = next(i for i in results_bad if i.invariant_id == "INV-1")
    assert inv1_bad.passed is False


def test_inv_2_acknowledged_write_missing():
    """Test INV-2: No Acknowledged Write Missing."""
    op = WriteOperation(txn_id="txn_202", key="acct_2", value="250", version=1, old_value="")
    disk = SimulatedDisk()
    snapshot = disk.snapshot()

    # 1. Write acknowledged, record missing -> FAIL
    results = check_invariants([], op, snapshot, write_was_acknowledged=True)
    inv2 = next(i for i in results if i.invariant_id == "INV-2")
    assert inv2.passed is False

    # 2. Write acknowledged, record recovered -> PASS
    rec = RecoveredRecord(key="acct_2", value="250", version=1, txn_id="txn_202")
    results_ok = check_invariants([rec], op, snapshot, write_was_acknowledged=True)
    inv2_ok = next(i for i in results_ok if i.invariant_id == "INV-2")
    assert inv2_ok.passed is True


def test_inv_3_uncommitted_partial_value_exposed():
    """Test INV-3: No Uncommitted Partial Value Exposed."""
    op = WriteOperation(txn_id="txn_303", key="acct_3", value="500", version=1, old_value="")
    
    disk = SimulatedDisk()
    disk.persisted["data_pages"]["blk_3"] = {"key": "acct_3", "value": "500", "version": 1, "txn_id": "txn_303"}
    disk.persisted["metadata_index"]["acct_3"] = {"block_id": "blk_3", "active": True, "txn_id": "txn_303"}
    # Commit marker is absent on disk

    # 1. Naive recovery exposes uncommitted record -> INV-3 FAILS
    naive_recs = naive_recover(disk)
    assert len(naive_recs) == 1
    naive_invs = check_invariants(naive_recs, op, disk.snapshot(), write_was_acknowledged=False)
    inv3_naive = next(i for i in naive_invs if i.invariant_id == "INV-3")
    assert inv3_naive.passed is False

    # 2. Safe recovery hides uncommitted record -> INV-3 PASSES
    safe_recs = safe_recover(disk)
    assert len(safe_recs) == 0
    safe_invs = check_invariants(safe_recs, op, disk.snapshot(), write_was_acknowledged=False)
    inv3_safe = next(i for i in safe_invs if i.invariant_id == "INV-3")
    assert inv3_safe.passed is True


def test_inv_4_checksum_integrity():
    """Test INV-4: Checksum Integrity."""
    op = WriteOperation(txn_id="txn_404", key="acct_4", value="999", version=1, old_value="")
    disk = SimulatedDisk()
    
    rec = RecoveredRecord(key="acct_4", value="999", version=1, txn_id="txn_404")
    valid_csum = _compute_checksum_from_record(rec)

    # 1. Valid checksum -> PASS
    disk.persisted["checksums"]["txn_404"] = valid_csum
    results_valid = check_invariants([rec], op, disk.snapshot(), write_was_acknowledged=False)
    inv4_valid = next(i for i in results_valid if i.invariant_id == "INV-4")
    assert inv4_valid.passed is True

    # 2. Corrupted/invalid checksum -> FAIL
    disk.persisted["checksums"]["txn_404"] = "crc32_corrupted123"
    results_bad = check_invariants([rec], op, disk.snapshot(), write_was_acknowledged=False)
    inv4_bad = next(i for i in results_bad if i.invariant_id == "INV-4")
    assert inv4_bad.passed is False


def run_invariant_tests() -> bool:
    """Run all invariant tests and return True if all pass."""
    tests = [
        ("INV-1", test_inv_1_valid_record_format),
        ("INV-2", test_inv_2_acknowledged_write_missing),
        ("INV-3", test_inv_3_uncommitted_partial_value_exposed),
        ("INV-4", test_inv_4_checksum_integrity),
    ]

    all_ok = True
    print("\n[2] INVARIANT TESTS")
    print("-" * 50)

    for name, func in tests:
        try:
            func()
            print(f"{name:<6} PASS")
        except Exception as e:
            print(f"{name:<6} FAIL — {e}")
            all_ok = False

    return all_ok


if __name__ == "__main__":
    success = run_invariant_tests()
    sys.exit(0 if success else 1)
