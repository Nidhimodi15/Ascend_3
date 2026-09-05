"""
test_agent.py — End-to-End integration test for Autonomous Root-Cause Investigator.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agent.agent import AutonomousInvestigationAgent


def run_agent_tests():
    print("\n--- Testing Autonomous Root-Cause Investigator Agent ---")
    results_summary = []

    # Test 1: Full investigation loop for Hook H10
    try:
        agent = AutonomousInvestigationAgent(max_experiments=20)
        report = agent.investigate(seed=48291, strategy="naive", initial_hook=10)

        assert report["status"] in ("ROOT_CAUSE_CONFIRMED", "ROOT_CAUSE_PLAUSIBLE", "INVESTIGATION_COMPLETE"), f"Unexpected status: {report['status']}"
        assert report["confidence"] == "HIGH", f"Expected HIGH confidence, got {report['confidence']}"
        assert report["total_experiments_executed"] >= 1, "Agent should run at least 1 experiment"
        assert report["total_experiments_executed"] < 12, "Agent should NOT force a full 12-hook sweep up-front"
        assert len(report["activity_log"]) > 0, "Activity log must not be empty"

        confirmed_name = report.get("confirmed_hypothesis")
        assert confirmed_name != "None", f"Expected confirmed hypothesis name, got {confirmed_name}"

        print("  [OK] Test 1: End-to-End Investigation for Hook 10 PASSED")
        results_summary.append(("Agent Investigation Hook 10", "PASS"))
    except Exception as e:
        print(f"  [X] Test 1 Failed: {e}")
        results_summary.append(("Agent Investigation Hook 10", "FAIL"))

    # Test 2: Dynamic initial observation budget sweep
    try:
        agent = AutonomousInvestigationAgent(max_experiments=20)
        report = agent.investigate(seed=48291, strategy="naive", initial_hook=None)  # Auto sweep

        assert report["status"] in ("ROOT_CAUSE_CONFIRMED", "ROOT_CAUSE_PLAUSIBLE", "INVESTIGATION_COMPLETE"), f"Unexpected status: {report['status']}"
        assert report["initial_hook_observed"] in list(range(1, 13)), f"Auto sweep should identify bug hook, got {report['initial_hook_observed']}"

        print("  [OK] Test 2: Auto Sweep Target Discovery PASSED")
        results_summary.append(("Agent Auto Sweep Discovery", "PASS"))
    except Exception as e:
        print(f"  [X] Test 2 Failed: {e}")
        results_summary.append(("Agent Auto Sweep Discovery", "FAIL"))

    # Test 3: Investigation for SAFE hook (H01)
    try:
        agent = AutonomousInvestigationAgent(max_experiments=20)
        report = agent.investigate(seed=48291, strategy="safe", initial_hook=1)

        assert report["status"] in ("ROOT_CAUSE_CONFIRMED", "ROOT_CAUSE_PLAUSIBLE", "INVESTIGATION_COMPLETE", "VERIFICATION_PASSED_SAFE"), f"Unexpected status: {report['status']}"

        print("  [OK] Test 3: Investigation for SAFE Hook 01 PASSED")
        results_summary.append(("Agent Investigation Safe Hook", "PASS"))
    except Exception as e:
        print(f"  [X] Test 3 Failed: {e}")
        results_summary.append(("Agent Investigation Safe Hook", "FAIL"))

    all_passed = all(st == "PASS" for _, st in results_summary)
    return all_passed, results_summary


if __name__ == "__main__":
    run_agent_tests()
