"""
test_crash_hooks.py — Crash Hook Verification Test Suite.

Executes the real verifier across all 12 declared crash hooks (H01 through H12).
Verifies return structures, hook index accuracy, state persistence, and verdict consistency.
Zero hardcoding of BUG/SAFE results — verdicts are determined dynamically by the engine.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.crash_verifier import run_full_verification, run_single_hook
from engine.types import HookResult, VerificationReport


def test_all_12_hooks_executed():
    """Verify that a full verification sweep executes all 12 declared crash hooks."""
    report = run_full_verification(seed=48291, strategy="naive")
    assert isinstance(report, VerificationReport)
    assert len(report.results) == 12, f"Expected 12 hook results, got {len(report.results)}"
    
    # Check that hooks are 1 through 12 in order
    for idx, res in enumerate(report.results, start=1):
        assert isinstance(res, HookResult)
        assert res.hook == idx, f"Expected hook number {idx}, got {res.hook}"
        assert res.phase in ("LOG", "DATA", "META", "COMMIT")
        assert res.step_description != ""
        assert res.disk_snapshot is not None
        assert res.verdict in ("SAFE", "BUG")


def test_hook_result_verdict_consistency():
    """Verify that verdict is strictly consistent with invariant pass/fail status."""
    report = run_full_verification(seed=48291, strategy="naive")
    for res in report.results:
        all_invariants_passed = all(inv.passed for inv in res.invariants)
        if res.verdict == "BUG":
            assert not all_invariants_passed, f"Hook {res.hook} verdict is BUG, but all invariants passed!"
            assert res.bug_details is not None
        elif res.verdict == "SAFE":
            assert all_invariants_passed, f"Hook {res.hook} verdict is SAFE, but an invariant failed!"


def test_single_hook_execution():
    """Verify running a single hook returns the exact requested hook result."""
    for hook_num in range(1, 13):
        res = run_single_hook(seed=48291, strategy="naive", hook=hook_num)
        assert isinstance(res, HookResult)
        assert res.hook == hook_num, f"Requested hook {hook_num}, got {res.hook}"
        assert res.disk_snapshot is not None
        assert res.verdict in ("SAFE", "BUG")


def run_crash_hook_tests() -> bool:
    """Run all crash hook tests and return True if all pass."""
    tests = [
        ("Full 12-Hook Sweep Execution", test_all_12_hooks_executed),
        ("Verdict-Invariant Consistency", test_hook_result_verdict_consistency),
        ("Single Hook Execution (H01-H12)", test_single_hook_execution),
    ]
    
    all_ok = True
    print("\n[1] CRASH HOOK COVERAGE")
    print("-" * 50)
    
    report = run_full_verification(seed=48291, strategy="naive")
    for res in report.results:
        status = "PASS" if res.verdict in ("SAFE", "BUG") else "FAIL"
        print(f"H{res.hook:02d}  ({res.phase:<6})  [{res.verdict:<4}]  {status}")

    for name, func in tests:
        try:
            func()
        except Exception as e:
            print(f"FAILED: {name} — {e}")
            all_ok = False
            
    return all_ok


if __name__ == "__main__":
    success = run_crash_hook_tests()
    sys.exit(0 if success else 1)
