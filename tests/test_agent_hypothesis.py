"""
test_agent_hypothesis.py — Unit tests for Agent Hypothesis Engine.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent.fingerprint import create_failure_fingerprint
from app.agent.hypothesis_engine import generate_competing_hypotheses
from app.agent.state_analyzer import analyze_hook_observation
from engine.crash_verifier import run_single_hook


def run_hypothesis_tests():
    print("\n--- Testing Agent Hypothesis Engine ---")
    results_summary = []

    # Test 1: Competing hypotheses formulation for COMMIT phase crash (H10)
    try:
        hook_res = run_single_hook(seed=48291, strategy="naive", hook=10)
        obs = analyze_hook_observation(hook_res)
        fp = create_failure_fingerprint(hook_res)
        hypotheses = generate_competing_hypotheses(obs, fp)

        assert len(hypotheses) >= 2, "Expected at least 2 competing hypotheses"
        assert any(h["id"] == "H1" for h in hypotheses), "Expected hypothesis H1"
        assert hypotheses[0]["name"] == "Missing Commit Validation", f"Unexpected top hypothesis: {hypotheses[0]['name']}"

        print("  [OK] Test 1: Competing Hypotheses for Hook 10 PASSED")
        results_summary.append(("Hypothesis Hook 10", "PASS"))
    except Exception as e:
        print(f"  [X] Test 1 Failed: {e}")
        results_summary.append(("Hypothesis Hook 10", "FAIL"))

    # Test 2: Competing hypotheses for DATA phase crash
    try:
        hook_res = run_single_hook(seed=48291, strategy="naive", hook=5)
        obs = analyze_hook_observation(hook_res)
        fp = create_failure_fingerprint(hook_res)
        hypotheses = generate_competing_hypotheses(obs, fp)

        assert len(hypotheses) >= 1, "Expected at least 1 hypothesis"
        print("  [OK] Test 2: Competing Hypotheses for Hook 05 PASSED")
        results_summary.append(("Hypothesis Hook 05", "PASS"))
    except Exception as e:
        print(f"  [X] Test 2 Failed: {e}")
        results_summary.append(("Hypothesis Hook 05", "FAIL"))

    all_passed = all(st == "PASS" for _, st in results_summary)
    return all_passed, results_summary


if __name__ == "__main__":
    run_hypothesis_tests()
