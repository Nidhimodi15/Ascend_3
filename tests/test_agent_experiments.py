"""
test_agent_experiments.py — Unit tests for Agent Experiment Selector & Runner.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent.fingerprint import create_failure_fingerprint
from app.agent.hypothesis_engine import generate_competing_hypotheses
from app.agent.state_analyzer import analyze_hook_observation
from app.agent.experiment_selector import select_next_experiment
from app.agent.experiment_runner import execute_experiment
from engine.crash_verifier import run_single_hook


def run_experiment_tests():
    print("\n--- Testing Agent Experiment Selector & Runner ---")
    results_summary = []

    # Test 1: Experiment selection based on Information Gain
    try:
        hook_res = run_single_hook(seed=48291, strategy="naive", hook=10)
        obs = analyze_hook_observation(hook_res)
        fp = create_failure_fingerprint(hook_res)
        hypotheses = generate_competing_hypotheses(obs, fp)

        exp = select_next_experiment(hypotheses, current_hook=10, completed_experiments=[])

        assert exp["experiment_type"] == "COMPARE_RECOVERY_STRATEGIES", f"Expected COMPARE_RECOVERY_STRATEGIES, got {exp['experiment_type']}"
        assert exp["information_score"] > 0.8, f"Expected high information gain score (>0.8), got {exp['information_score']}"

        print("  [OK] Test 1: Information Gain Experiment Selection PASSED")
        results_summary.append(("Information Gain Selection", "PASS"))
    except Exception as e:
        print(f"  [X] Test 1 Failed: {e}")
        results_summary.append(("Information Gain Selection", "FAIL"))

    # Test 2: Experiment execution using real engine
    try:
        exp = {
            "experiment_type": "COMPARE_RECOVERY_STRATEGIES",
            "target_hook": 10,
            "information_score": 0.95,
            "reason": "Test compare recovery strategies"
        }

        exp_result = execute_experiment(
            experiment=exp,
            seed=48291,
            strategy="naive"
        )

        assert exp_result["experiment_type"] == "COMPARE_RECOVERY_STRATEGIES", "Wrong experiment name in result"
        assert exp_result["target_hook"] == 10, "Target hook mismatch"
        assert "evidence_summary" in exp_result, "Result missing evidence summary"
        assert exp_result.get("safe_verdict") == "SAFE", "Safe recovery for H10 should yield SAFE verdict"

        print("  [OK] Test 2: Real Engine Experiment Execution PASSED")
        results_summary.append(("Experiment Execution", "PASS"))
    except Exception as e:
        print(f"  [X] Test 2 Failed: {e}")
        results_summary.append(("Experiment Execution", "FAIL"))

    all_passed = all(st == "PASS" for _, st in results_summary)
    return all_passed, results_summary


if __name__ == "__main__":
    run_experiment_tests()
