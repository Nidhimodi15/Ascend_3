"""
experiment_selector.py — Information Gain Experiment Selector.

Ranks and selects the next experiment that maximizes Information Gain
to eliminate competing hypotheses and strengthen confirmed findings.
"""
from typing import List, Dict, Any


def calculate_information_scores(
    hypotheses: List[Dict[str, Any]],
    current_hook: int,
    completed_experiments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Calculate information gain scores for candidate experiments based on untested/competing hypotheses.
    """
    completed_types = {e.get("experiment_type") for e in completed_experiments}
    untested_cats = {h["category"] for h in hypotheses if h["status"] == "UNTESTED"}

    candidates = []

    # 1. Compare Recovery Strategies (Safe vs Naive) -> Tests if enforcing commit marker eliminates failure
    if "COMMIT_VALIDATION" in untested_cats or "CHECKSUM_VALIDATION" in untested_cats:
        score = 0.95 if "COMPARE_RECOVERY_STRATEGIES" not in completed_types else 0.40
        candidates.append({
            "experiment_type": "COMPARE_RECOVERY_STRATEGIES",
            "target_hook": current_hook,
            "information_score": score,
            "reason": f"Compare Safe Recovery against current hook {current_hook} to test if enforcing commit validation eliminates record exposure.",
        })

    # 2. Inspect Neighboring Hooks -> Tests if pattern spans across the phase
    neighbor_hooks = [h for h in (current_hook - 1, current_hook + 1) if 1 <= h <= 12]
    if neighbor_hooks:
        target_neighbor = neighbor_hooks[0]
        score = 0.85 if "COMPARE_NEIGHBORING_HOOK" not in completed_types else 0.50
        candidates.append({
            "experiment_type": "COMPARE_NEIGHBORING_HOOK",
            "target_hook": target_neighbor,
            "information_score": score,
            "reason": f"Inspect neighboring crash hook H{target_neighbor:02d} to test if the failure pattern spans across the execution phase.",
        })

    # 3. Verify Prevention Rule -> Tests rule generator output for failure fingerprint
    if "VERIFY_PREVENTION_RULE" not in completed_types:
        candidates.append({
            "experiment_type": "VERIFY_PREVENTION_RULE",
            "target_hook": current_hook,
            "information_score": 0.75,
            "reason": f"Evaluate automated prevention recommendation engine against failure fingerprint of hook {current_hook}.",
        })

    # 4. Replay Same Seed -> Tests deterministic reproducibility
    if "REPLAY_SAME_SEED" not in completed_types:
        candidates.append({
            "experiment_type": "REPLAY_SAME_SEED",
            "target_hook": current_hook,
            "information_score": 0.60,
            "reason": f"Re-run hook {current_hook} under identical seed to confirm 100% deterministic reproduction.",
        })

    # Sort descending by information_score
    candidates.sort(key=lambda x: x["information_score"], reverse=True)
    return candidates


def select_next_experiment(
    hypotheses: List[Dict[str, Any]],
    current_hook: int,
    completed_experiments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Select the highest-value experiment based on information gain scoring.
    """
    scores = calculate_information_scores(hypotheses, current_hook, completed_experiments)
    if scores:
        return scores[0]
    
    # Fallback experiment
    return {
        "experiment_type": "COMPARE_NEIGHBORING_HOOK",
        "target_hook": min(current_hook + 1, 12),
        "information_score": 0.50,
        "reason": "Inspect next crash hook for additional evidence.",
    }
