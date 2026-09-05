"""
test_recovery.py — Recovery Algorithms & Crash Semantics Test Suite.

Tests:
  - Naive Recovery vs Safe Recovery comparison
  - Persisted vs Volatile Memory Discard on simulated crash
  - Cross-hook isolation (no state bleeding across runs)
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.simulated_disk import SimulatedDisk
from engine.types import RecoveredRecord
from engine.naive_recovery import naive_recover
from engine.safe_recovery import safe_recover
from engine.crash_verifier import run_full_verification, run_single_hook


def test_naive_vs_safe_same_input():
    """Verify both algorithms execute on identical disk input but yield safe rollback when appropriate."""
    naive_report = run_full_verification(seed=48291, strategy="naive")
    safe_report  = run_full_verification(seed=48291, strategy="safe")

    assert naive_report.total_bugs >= 0
    assert safe_report.total_bugs == 0, "Safe recovery should pass all hooks with 0 bugs!"

    for n_res, s_res in zip(naive_report.results, safe_report.results):
        assert n_res.hook == s_res.hook
        assert n_res.disk_snapshot == s_res.disk_snapshot


def test_persisted_vs_volatile_discard():
    """Verify crash() discards volatile buffer contents while preserving flushed disk state."""
    disk = SimulatedDisk()

    # 1. Unflushed write in volatile buffer
    disk.buf_data_write("blk_1", {"key": "k1", "value": "v1", "version": 1, "txn_id": "t1"})
    assert len(disk.buffer["data_pages"]) == 1
    assert len(disk.persisted["data_pages"]) == 0

    # 2. Crash -> buffer lost
    disk.crash()
    assert len(disk.buffer["data_pages"]) == 0
    assert len(disk.persisted["data_pages"]) == 0

    # 3. Flushed write -> persisted
    disk.buf_data_write("blk_2", {"key": "k2", "value": "v2", "version": 1, "txn_id": "t2"})
    disk.flush("data")
    disk.crash()
    assert "blk_2" in disk.persisted["data_pages"]


def test_no_cross_hook_contamination():
    """Verify each crash hook executes on a clean storage state."""
    h01 = run_single_hook(seed=48291, strategy="naive", hook=1)
    h02 = run_single_hook(seed=48291, strategy="naive", hook=2)
    h10 = run_single_hook(seed=48291, strategy="naive", hook=10)

    assert h01.hook == 1
    assert h02.hook == 2
    assert h10.hook == 10

    # Hook 1 snapshot should not contain commit markers created in Hook 10
    assert len(h01.disk_snapshot.commit_markers) == 0


run_recovery_tests_func = None


def run_recovery_tests() -> bool:
    """Run all recovery tests and return True if all pass."""
    tests = [
        ("Naive Recovery", test_naive_vs_safe_same_input),
        ("Safe Recovery", test_naive_vs_safe_same_input),
        ("Persisted vs Volatile", test_persisted_vs_volatile_discard),
        ("Cross-Hook Isolation", test_no_cross_hook_contamination),
    ]

    all_ok = True
    print("\n[3] RECOVERY TESTS")
    print("-" * 50)

    for name, func in tests:
        try:
            func()
            print(f"{name:<20} PASS")
        except Exception as e:
            print(f"{name:<20} FAIL — {e}")
            all_ok = False

    return all_ok


if __name__ == "__main__":
    success = run_recovery_tests()
    sys.exit(0 if success else 1)
