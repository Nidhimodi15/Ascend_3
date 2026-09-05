"""
run_tests.py — Master Console Test Runner for KillPoint Engine.

Runs Phase 1 (Core Engine & Invariants), Phase 2 (Edge Cases & Storage Failures),
and Phase 3 (Autonomous Root-Cause Investigator Agent).
Exits with code 0 if all non-skipped tests pass, or code 1 if any test fails.
"""
import sys
import os

# Ensure d:\ascend_3 is in import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_crash_hooks import run_crash_hook_tests
from tests.test_invariants import run_invariant_tests
from tests.test_recovery import run_recovery_tests
from tests.test_determinism import run_determinism_tests
from tests.test_prevention import run_prevention_tests
from tests.test_edge_cases import run_edge_case_tests
from tests.test_storage_failures import run_storage_failure_tests
from tests.test_agent_fingerprint import run_fingerprint_tests
from tests.test_agent_hypothesis import run_hypothesis_tests
from tests.test_agent_experiments import run_experiment_tests
from tests.test_agent import run_agent_tests


def main():
    print("=" * 50)
    print(" KILLPOINT CONSOLE TEST SUITE")
    print("=" * 50)

    # ─── PHASE 1 ─────────────────────────────────────────────────────────────
    print("\n[PHASE 1] CORE ENGINE & INVARIANT TESTS")
    print("=" * 50)

    p1_results = []
    p1_results.append(("Crash Hook Coverage", run_crash_hook_tests()))
    p1_results.append(("Invariant Tests", run_invariant_tests()))
    p1_results.append(("Recovery Tests", run_recovery_tests()))
    p1_results.append(("Determinism Tests", run_determinism_tests()))
    p1_results.append(("Prevention Tests", run_prevention_tests()))

    phase1_passed = all(status for _, status in p1_results)

    # ─── PHASE 2 ─────────────────────────────────────────────────────────────
    print("\n\n" + "=" * 50)
    print("[PHASE 2] EDGE CASE & ROBUSTNESS TESTS")
    print("=" * 50)

    p2_edge_ok, p2_edge_summary = run_edge_case_tests()
    p2_storage_ok, p2_storage_summary = run_storage_failure_tests()

    phase2_passed = p2_edge_ok and p2_storage_ok

    # ─── PHASE 3 ─────────────────────────────────────────────────────────────
    print("\n\n" + "=" * 50)
    print("[PHASE 3] AUTONOMOUS ROOT-CAUSE INVESTIGATOR TESTS")
    print("=" * 50)

    p3_fp_ok, p3_fp_sum = run_fingerprint_tests()
    p3_hypo_ok, p3_hypo_sum = run_hypothesis_tests()
    p3_exp_ok, p3_exp_sum = run_experiment_tests()
    p3_agent_ok, p3_agent_sum = run_agent_tests()

    phase3_passed = p3_fp_ok and p3_hypo_ok and p3_exp_ok and p3_agent_ok
    p3_all_summary = p3_fp_sum + p3_hypo_sum + p3_exp_sum + p3_agent_sum

    # Calculate statistics
    p2_all_summary = p2_edge_summary + p2_storage_summary
    total_passed = sum(1 for _, st in p2_all_summary if st == "PASS") + sum(1 for _, st in p3_all_summary if st == "PASS") + 16  # 16 tests in Phase 1
    total_failed = sum(1 for _, st in p2_all_summary if st == "FAIL") + sum(1 for _, st in p3_all_summary if st == "FAIL") + sum(1 for _, st in p1_results if not st)
    total_skipped = sum(1 for _, st in p2_all_summary if st == "SKIP")

    print("\n" + "=" * 50)
    print("FINAL TEST SUMMARY")
    print("=" * 50)
    print(f"Phase 1 Result : {'ALL PASSED' if phase1_passed else 'FAILED'}")
    print(f"Phase 2 Result : {'ALL PASSED' if phase2_passed else 'FAILED'} ({total_skipped} SKIPPED)")
    print(f"Phase 3 Result : {'ALL PASSED' if phase3_passed else 'FAILED'}")
    print(f"Total Passed   : {total_passed}")
    print(f"Total Failed   : {total_failed}")
    print(f"Total Skipped  : {total_skipped}")
    print("=" * 50)

    if phase1_passed and phase2_passed and phase3_passed:
        print("ALL TESTS PASSED")
        print("=" * 50)
        sys.exit(0)
    else:
        print("TEST SUITE FAILED — See output above for details")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()

