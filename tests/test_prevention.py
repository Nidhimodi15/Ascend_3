"""
test_prevention.py — Prevention Suggestions Test Suite.

Verifies:
  - BUG hook with missing commit marker (INV-3) -> generates ROLL BACK / HIDE RECORD suggestion.
  - BUG hook with checksum mismatch (INV-4) -> generates REJECT RECORD suggestion.
  - SAFE hook -> returns None (no prevention suggestion shown).
  - Suggestions are evaluated strictly from runtime invariant failure objects and disk snapshots.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.crash_verifier import run_single_hook
from app.security.prevention_rules import get_prevention_suggestion
from engine.types import InvariantResult, DiskSnapshot, RecoveredRecord


def test_bug_inv3_prevention_suggestion():
    """Verify BUG hook caused by missing commit marker generates commit rule suggestion."""
    h10_res = run_single_hook(seed=48291, strategy="naive", hook=10)
    assert h10_res.verdict == "BUG"

    sug = get_prevention_suggestion(h10_res.invariants, h10_res.disk_snapshot, h10_res.recovered_records)
    assert sug is not None
    assert "Commit marker is missing" in sug["problem"]
    assert "Commit Marker is VALID" in sug["rule"]
    assert sug["action"] == "ROLL BACK / HIDE RECORD"


def test_bug_inv4_checksum_prevention_suggestion():
    """Verify BUG hook caused by checksum mismatch generates checksum rejection suggestion."""
    inv4_fail = [
        InvariantResult(
            invariant_id="INV-4",
            name="Checksum Integrity",
            passed=False,
            expected="Stored == Computed",
            actual="Checksum MISMATCH detected",
            details="Checksum error on disk",
        )
    ]
    
    sug = get_prevention_suggestion(inv4_fail, None, None)
    assert sug is not None
    assert "checksum" in sug["problem"].lower()
    assert "checksum verification succeeds" in sug["rule"].lower()
    assert sug["action"] == "REJECT RECORD"


def test_safe_hook_no_prevention_suggestion():
    """Verify SAFE hook yields None for prevention suggestion."""
    h01_res = run_single_hook(seed=48291, strategy="naive", hook=1)
    assert h01_res.verdict == "SAFE"

    sug = get_prevention_suggestion(h01_res.invariants, h01_res.disk_snapshot, h01_res.recovered_records)
    assert sug is None


def test_suggestion_based_on_actual_runtime_state():
    """Verify prevention suggestion changes dynamically based on invariant object, not raw hook index."""
    # Even if hook 1 is passed in, if passed invariants are supplied, it returns None
    h01_res = run_single_hook(seed=48291, strategy="safe", hook=10)
    assert h01_res.verdict == "SAFE"
    assert get_prevention_suggestion(h01_res.invariants, h01_res.disk_snapshot, h01_res.recovered_records) is None


def run_prevention_tests() -> bool:
    """Run all prevention tests and return True if all pass."""
    tests = [
        ("BUG -> prevention suggestion", test_bug_inv3_prevention_suggestion),
        ("SAFE -> no suggestion", test_safe_hook_no_prevention_suggestion),
        ("Suggestion based on actual state", test_suggestion_based_on_actual_runtime_state),
    ]

    all_ok = True
    print("\n[5] PREVENTION TESTS")
    print("-" * 50)

    for name, func in tests:
        try:
            func()
            print(f"{name:<36} PASS")
        except Exception as e:
            print(f"{name:<36} FAIL — {e}")
            all_ok = False

    return all_ok


if __name__ == "__main__":
    success = run_prevention_tests()
    sys.exit(0 if success else 1)
