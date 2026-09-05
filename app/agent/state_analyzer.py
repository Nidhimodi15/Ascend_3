"""
state_analyzer.py — State Analyzer for Agent Observations.

Analyzes raw HookResult structures and extracts structured observation maps for the agent.
"""
from typing import Dict, Any
from engine.types import HookResult
from app.agent.fingerprint import create_failure_fingerprint


def analyze_hook_observation(hook_result: HookResult) -> Dict[str, Any]:
    """
    Analyze a HookResult and produce a structured observation map.
    """
    fp = create_failure_fingerprint(hook_result)
    failed_invs = [inv for inv in hook_result.invariants if not inv.passed]

    return {
        "hook": hook_result.hook,
        "phase": hook_result.phase,
        "step_description": hook_result.step_description,
        "verdict": hook_result.verdict,
        "fingerprint": fp,
        "exposed_records_count": len(hook_result.recovered_records),
        "failed_invariants": [inv.invariant_id for inv in failed_invs],
        "bug_details": hook_result.bug_details,
    }
