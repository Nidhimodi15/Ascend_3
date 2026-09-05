"""
report_generator.py — Investigation Report Generator.

Formats structured investigation reports referencing actual experiment evidence.
"""
from typing import Dict, Any


def generate_investigation_report(agent_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a complete, evidence-backed root cause report from AgentState.
    """
    confirmed_h = next((h for h in agent_state["hypotheses"] if h["status"] in ("CONFIRMED", "STRENGTHENED")), None)
    rejected_hs = [h for h in agent_state["hypotheses"] if h["status"] == "REJECTED"]

    return {
        "investigation_id": agent_state.get("id", "inv_001"),
        "seed": agent_state["seed"],
        "strategy": agent_state["strategy"],
        "status": agent_state["status"],
        "total_experiments_executed": len(agent_state["experiments"]),
        "initial_hook_observed": agent_state.get("initial_hook"),
        "failure_families": agent_state.get("failure_families", []),
        "hypotheses": agent_state["hypotheses"],
        "confirmed_hypothesis": confirmed_h["name"] if confirmed_h else "None",
        "rejected_hypotheses": [h["name"] for h in rejected_hs],
        "confidence": agent_state["confidence"],
        "confidence_score": agent_state.get("confidence_score", 0.0),
        "root_cause": agent_state["final_root_cause"],
        "recommended_prevention": {
            "rule": "Never expose a recovered record unless the Commit Marker is VALID.",
            "suggested_action": "ROLL BACK / HIDE RECORD",
        },
        "evidence_summary": [e.get("evidence_summary") for e in agent_state["experiments"] if e.get("evidence_summary")],
        "activity_log": agent_state["activity_log"],
    }
