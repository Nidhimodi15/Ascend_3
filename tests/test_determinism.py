"""
test_determinism.py — Determinism & Repeatability Test Suite.

Verifies:
  - Same seed -> identical WriteOperation generated every time.
  - Same seed + hook + strategy -> identical DiskSnapshot, Invariants, and Verdict.
  - Different seeds generate distinct operation payloads.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.seeded_random import generate_operation
from engine.crash_verifier import run_single_hook


def test_same_seed_same_operation():
    """Verify same seed produces identical WriteOperation."""
    op1 = generate_operation(seed=42)
    op2 = generate_operation(seed=42)
    
    assert op1.txn_id == op2.txn_id
    assert op1.key == op2.key
    assert op1.value == op2.value
    assert op1.version == op2.version
    assert op1.old_value == op2.old_value


def test_same_seed_same_persisted_state_and_result():
    """Verify same seed + hook + strategy produces identical verification outputs across multiple runs."""
    run1 = run_single_hook(seed=42, strategy="naive", hook=10)
    run2 = run_single_hook(seed=42, strategy="naive", hook=10)
    run3 = run_single_hook(seed=42, strategy="naive", hook=10)

    assert run1.hook == run2.hook == run3.hook == 10
    assert run1.verdict == run2.verdict == run3.verdict
    assert run1.disk_snapshot == run2.disk_snapshot == run3.disk_snapshot
    assert run1.recovered_records == run2.recovered_records == run3.recovered_records
    assert run1.invariants == run2.invariants == run3.invariants


def test_different_seeds_distinct_payloads():
    """Verify different seeds generate different transaction/key payloads."""
    op_a = generate_operation(seed=42)
    op_b = generate_operation(seed=99)

    assert (op_a.key, op_a.value, op_a.txn_id) != (op_b.key, op_b.value, op_b.txn_id)


def run_determinism_tests() -> bool:
    """Run all determinism tests and return True if all pass."""
    tests = [
        ("Same seed -> same operation", test_same_seed_same_operation),
        ("Same seed -> same persisted state", test_same_seed_same_persisted_state_and_result),
        ("Same seed -> same result", test_same_seed_same_persisted_state_and_result),
    ]

    all_ok = True
    print("\n[4] DETERMINISM TESTS")
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
    success = run_determinism_tests()
    sys.exit(0 if success else 1)
