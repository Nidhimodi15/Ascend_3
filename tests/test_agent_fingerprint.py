"""
test_agent_fingerprint.py — Unit tests for Agent Fingerprint Engine.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent.fingerprint import create_failure_fingerprint
from engine.crash_verifier import run_single_hook


def run_fingerprint_tests():
    print("\n--- Testing Agent Fingerprint Generator ---")
    results_summary = []

    # Test 1: Fingerprint creation for H10 (Naive)
    try:
        hook_res = run_single_hook(seed=48291, strategy="naive", hook=10)
        fp = create_failure_fingerprint(hook_res)

        assert isinstance(fp, dict), "Expected dictionary instance"
        assert fp.get("verdict") == "BUG", "Expected verdict BUG"
        assert fp.get("inv3") == "FAIL", "Expected INV-3 to fail"
        assert fp.get("hash") != "", "Expected non-empty fingerprint hash"
        assert fp.get("data_present") is True, "Expected data page to be present"
        assert fp.get("commit_present") is False, "Expected commit marker to be missing"

        print("  [OK] Test 1: Fingerprint creation for Hook 10 (Naive) PASSED")
        results_summary.append(("Fingerprint Hook 10 Naive", "PASS"))
    except Exception as e:
        print(f"  [X] Test 1 Failed: {e}")
        results_summary.append(("Fingerprint Hook 10 Naive", "FAIL"))

    # Test 2: Fingerprint deterministic hash reproducibility
    try:
        hook_res1 = run_single_hook(seed=48291, strategy="naive", hook=10)
        hook_res2 = run_single_hook(seed=48291, strategy="naive", hook=10)

        fp1 = create_failure_fingerprint(hook_res1)
        fp2 = create_failure_fingerprint(hook_res2)

        assert fp1["hash"] == fp2["hash"], "Fingerprint hash must be deterministic"
        print("  [OK] Test 2: Fingerprint Determinism PASSED")
        results_summary.append(("Fingerprint Hash Determinism", "PASS"))
    except Exception as e:
        print(f"  [X] Test 2 Failed: {e}")
        results_summary.append(("Fingerprint Hash Determinism", "FAIL"))

    # Test 3: Fingerprint creation for SAFE hook (H01)
    try:
        hook_res_safe = run_single_hook(seed=48291, strategy="naive", hook=1)
        fp_safe = create_failure_fingerprint(hook_res_safe)

        assert fp_safe.get("verdict") == "SAFE", "Expected verdict SAFE"
        assert fp_safe.get("inv1") == "PASS" and fp_safe.get("inv3") == "PASS", "Expected all invariants to pass"

        print("  [OK] Test 3: Fingerprint for SAFE Hook 01 PASSED")
        results_summary.append(("Fingerprint Hook 01 Safe", "PASS"))
    except Exception as e:
        print(f"  [X] Test 3 Failed: {e}")
        results_summary.append(("Fingerprint Hook 01 Safe", "FAIL"))

    all_passed = all(st == "PASS" for _, st in results_summary)
    return all_passed, results_summary


if __name__ == "__main__":
    run_fingerprint_tests()
