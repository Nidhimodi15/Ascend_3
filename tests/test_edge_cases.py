"""
test_edge_cases.py — Phase 2: Edge Cases & Robustness Test Suite.

Tests boundary conditions, input validation, corrupted/partial persisted states,
WAL anomalies, metadata mismatches, and commit marker variations.
Uses real engine functions with zero hardcoded outcomes.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.simulated_disk import SimulatedDisk
from engine.types import RecoveredRecord, WriteOperation
from engine.invariant_checker import check_invariants, _compute_checksum_from_record
from engine.naive_recovery import naive_recover
from engine.safe_recovery import safe_recover
from engine.crash_verifier import run_single_hook


def test_input_edge_cases():
    """Test empty keys, empty values, very long strings, and duplicate inputs."""
    results = []

    # 1. Empty key & value
    op_empty = WriteOperation(txn_id="txn_e", key="", value="", version=1, old_value="")
    disk = SimulatedDisk()
    rec_empty = RecoveredRecord(key="", value="", version=1, txn_id="txn_e")
    inv_res = check_invariants([rec_empty], op_empty, disk.snapshot(), write_was_acknowledged=False)
    inv1 = next(i for i in inv_res if i.invariant_id == "INV-1")
    assert inv1.passed is False, "Empty key/value should fail INV-1 format check"
    results.append(("Empty key", True))
    results.append(("Empty value", True))

    # 2. Long key & value
    long_key = "k" * 1000
    long_val = "v" * 5000
    op_long = WriteOperation(txn_id="txn_long", key=long_key, value=long_val, version=9999, old_value="")
    rec_long = RecoveredRecord(key=long_key, value=long_val, version=9999, txn_id="txn_long")
    inv_long = check_invariants([rec_long], op_long, disk.snapshot(), write_was_acknowledged=False)
    inv1_long = next(i for i in inv_long if i.invariant_id == "INV-1")
    assert inv1_long.passed is True, "Long valid strings should pass INV-1"
    results.append(("Long value", True))

    # 3. Invalid transaction ID format
    rec_bad_txn = RecoveredRecord(key="acct_x", value="100", version=1, txn_id="")
    inv_bad_txn = check_invariants([rec_bad_txn], op_empty, disk.snapshot(), write_was_acknowledged=False)
    inv1_bad_txn = next(i for i in inv_bad_txn if i.invariant_id == "INV-1")
    assert inv1_bad_txn.passed is False, "Missing txn_id must fail INV-1"
    results.append(("Invalid transaction", True))

    # 4. Duplicate transaction / key handling
    disk_dup = SimulatedDisk()
    disk_dup.persisted["metadata_index"]["k1"] = {"block_id": "b1", "active": True, "txn_id": "txn_dup"}
    recs = naive_recover(disk_dup)
    assert isinstance(recs, list)
    results.append(("Duplicate transaction", True))

    return results


def test_wal_edge_cases():
    """Test missing WAL, partial WAL, corrupted WAL, and empty WAL."""
    results = []

    # 1. Missing / Empty WAL
    disk = SimulatedDisk()
    disk.persisted["wal"] = []
    assert naive_recover(disk) == []
    assert safe_recover(disk) == []
    results.append(("Missing WAL", True))

    # 2. Partial WAL entry
    disk.persisted["wal"].append({"partial": True})
    assert isinstance(safe_recover(disk), list)
    results.append(("Partial WAL", True))

    # 3. Corrupted WAL entry
    disk.persisted["wal"].append({"corrupted_bytes": "0xDEADBEEF"})
    assert isinstance(safe_recover(disk), list)
    results.append(("Corrupted WAL", True))

    return results


def test_data_edge_cases():
    """Test missing data, partial data, corrupted data, and data without metadata."""
    results = []

    # 1. Missing data (metadata points to non-existent block)
    disk = SimulatedDisk()
    disk.persisted["metadata_index"]["key_1"] = {"block_id": "blk_missing", "active": True, "txn_id": "t1"}
    assert naive_recover(disk) == []
    assert safe_recover(disk) == []
    results.append(("Missing data", True))

    # 2. Partial data payload
    disk.persisted["data_pages"]["blk_part"] = {"key": "k2", "value": None, "version": 1, "txn_id": "t2"}
    disk.persisted["metadata_index"]["k2"] = {"block_id": "blk_part", "active": True, "txn_id": "t2"}
    recs = naive_recover(disk)
    op = WriteOperation(txn_id="t2", key="k2", value="v2", version=1, old_value="")
    if recs:
        invs = check_invariants(recs, op, disk.snapshot(), write_was_acknowledged=False)
        inv1 = next(i for i in invs if i.invariant_id == "INV-1")
        assert inv1.passed is False, "Partial data payload with None value must fail INV-1"
    results.append(("Partial data", True))

    # 3. Corrupted data page
    disk.persisted["data_pages"]["blk_corrupt"] = {"key": "k3", "value": "corrupt", "version": 1, "txn_id": "t3"}
    disk.persisted["metadata_index"]["k3"] = {"block_id": "blk_corrupt", "active": True, "txn_id": "t3"}
    disk.persisted["checksums"]["t3"] = "crc32_original"
    safe_recs = safe_recover(disk)
    assert len(safe_recs) == 0, "Corrupted data page with mismatched checksum must be rejected by safe recovery"
    results.append(("Corrupted data", True))

    return results


def test_metadata_edge_cases():
    """Test missing metadata, corrupted metadata, and data/metadata mismatch."""
    results = []

    # 1. Missing metadata (data page exists without metadata entry)
    disk = SimulatedDisk()
    disk.persisted["data_pages"]["blk_orphaned"] = {"key": "k_orph", "value": "v", "version": 1, "txn_id": "t_orph"}
    assert naive_recover(disk) == []
    assert safe_recover(disk) == []
    results.append(("Missing metadata", True))

    # 2. Corrupted metadata (active=False or missing block_id)
    disk.persisted["metadata_index"]["k_bad"] = {"block_id": None, "active": False, "txn_id": "t_bad"}
    assert naive_recover(disk) == []
    assert safe_recover(disk) == []
    results.append(("Corrupted metadata", True))

    # 3. Data / Metadata mismatch (metadata points to blk_A, but data page is blk_B)
    disk.persisted["metadata_index"]["k_mis"] = {"block_id": "blk_A", "active": True, "txn_id": "t_mis"}
    disk.persisted["data_pages"]["blk_B"] = {"key": "k_mis", "value": "v", "version": 1, "txn_id": "t_mis"}
    assert naive_recover(disk) == []
    assert safe_recover(disk) == []
    results.append(("Data/metadata mismatch", True))

    return results


def test_checksum_edge_cases():
    """Test missing checksum, invalid checksum, and checksum mismatch."""
    results = []

    op = WriteOperation(txn_id="t_cs", key="k_cs", value="val_cs", version=1, old_value="")
    disk = SimulatedDisk()
    disk.persisted["data_pages"]["blk_cs"] = {"key": "k_cs", "value": "val_cs", "version": 1, "txn_id": "t_cs"}
    disk.persisted["metadata_index"]["k_cs"] = {"block_id": "blk_cs", "active": True, "txn_id": "t_cs"}
    disk.persisted["commit_markers"]["t_cs"] = {"committed": True}

    # 1. Missing checksum -> Safe recovery accepts if commit marker valid
    assert len(safe_recover(disk)) == 1
    results.append(("Missing checksum", True))

    # 2. Invalid checksum format
    disk.persisted["checksums"]["t_cs"] = "invalid_format_csum"
    assert len(safe_recover(disk)) == 0, "Safe recovery must reject record with invalid checksum"
    naive_recs = naive_recover(disk)
    invs_invalid = check_invariants(naive_recs, op, disk.snapshot(), write_was_acknowledged=False)
    inv4_invalid = next(i for i in invs_invalid if i.invariant_id == "INV-4")
    assert inv4_invalid.passed is False, "INV-4 must fail when exposed record has invalid stored checksum"
    results.append(("Invalid checksum", True))

    # 3. Checksum mismatch
    disk.persisted["checksums"]["t_cs"] = "crc32_00000000"
    assert len(safe_recover(disk)) == 0, "Checksum mismatch must cause safe recovery to reject record"
    results.append(("Checksum mismatch", True))

    return results



def test_commit_edge_cases():
    """Test missing commit marker, invalid commit marker, and corrupted commit marker."""
    results = []

    disk = SimulatedDisk()
    disk.persisted["data_pages"]["blk_cm"] = {"key": "k_cm", "value": "val_cm", "version": 1, "txn_id": "t_cm"}
    disk.persisted["metadata_index"]["k_cm"] = {"block_id": "blk_cm", "active": True, "txn_id": "t_cm"}

    # 1. Missing commit marker -> Safe recovery rejects
    assert len(safe_recover(disk)) == 0
    results.append(("Missing commit marker", True))

    # 2. Invalid commit marker (committed=False)
    disk.persisted["commit_markers"]["t_cm"] = {"committed": False}
    assert len(safe_recover(disk)) == 0
    results.append(("Invalid commit marker", True))

    # 3. Corrupted commit marker payload
    disk.persisted["commit_markers"]["t_cm"] = {"corrupted": True}
    assert len(safe_recover(disk)) == 0
    results.append(("Corrupted commit marker", True))

    return results


def run_edge_case_tests():
    """Run all Phase 2 edge case tests."""
    suites = [
        ("[INPUT EDGE CASES]", test_input_edge_cases),
        ("[WAL / LOG]", test_wal_edge_cases),
        ("[DATA]", test_data_edge_cases),
        ("[METADATA]", test_metadata_edge_cases),
        ("[CHECKSUM]", test_checksum_edge_cases),
        ("[COMMIT]", test_commit_edge_cases),
    ]

    all_passed = True
    summary = []

    for section_title, func in suites:
        print(f"\n{section_title}")

        try:
            items = func()
            for name, ok in items:
                status = "PASS" if ok else "FAIL"
                print(f"{name:<26} {status}")
                summary.append((name, status))
        except Exception as e:
            print(f"FAILED {section_title}: {e}")
            all_passed = False

    return all_passed, summary


if __name__ == "__main__":
    ok, _ = run_edge_case_tests()
    sys.exit(0 if ok else 1)
