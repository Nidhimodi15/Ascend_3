"""
hypothesis_engine.py — Competing Hypothesis Formulation Engine.

Generates multiple competing candidate hypotheses from empirical runtime failure evidence:
  H1: Commit marker validation failure
  H2: Checksum validation failure
  H3: Metadata pointer / payload structure inconsistency

No external LLM or AI API used — purely local, evidence-driven hypothesis formulation.
"""
from typing import List, Dict, Any


def generate_competing_hypotheses(observation: Dict[str, Any], fingerprint: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Formulate candidate competing hypotheses based on observed failure fingerprint.
    """
    hypotheses = []
    inv3_failed = fingerprint.get("inv3") == "FAIL"
    inv4_failed = fingerprint.get("inv4") == "FAIL"
    inv1_failed = fingerprint.get("inv1") == "FAIL"
    commit_missing = not fingerprint.get("commit_present")

    if inv3_failed or commit_missing:
        hypotheses.append({
            "id": "H1",
            "name": "Missing Commit Validation",
            "statement": "Recovery algorithm exposes uncommitted persisted state without validating the durable commit marker.",
            "category": "COMMIT_VALIDATION",
            "status": "UNTESTED",
            "evidence": [f"Observed {observation.get('step_description', 'crash hook')} with missing commit marker exposing record."],
            "score": 0.5,
        })
        hypotheses.append({
            "id": "H2",
            "name": "Checksum Verification Mismatch",
            "statement": "Failure is primarily caused by unverified or missing payload checksums during record reconstruction.",
            "category": "CHECKSUM_VALIDATION",
            "status": "UNTESTED",
            "evidence": ["Candidate explanation: Checksum integrity failure might account for unvalidated record exposure."],
            "score": 0.5,
        })
        hypotheses.append({
            "id": "H3",
            "name": "Metadata Index Corruption",
            "statement": "Metadata index entry remains active when data page write is incomplete.",
            "category": "METADATA_VALIDATION",
            "status": "UNTESTED",
            "evidence": ["Candidate explanation: Metadata pointer persistence might be out of sync with write path."],
            "score": 0.5,
        })
    elif inv4_failed:
        hypotheses.append({
            "id": "H2",
            "name": "Checksum Verification Mismatch",
            "statement": "Stored checksum on persisted disk does not match recovered record payload.",
            "category": "CHECKSUM_VALIDATION",
            "status": "UNTESTED",
            "evidence": ["Checksum invariant (INV-4) explicitly failed."],
            "score": 0.5,
        })
        hypotheses.append({
            "id": "H1",
            "name": "Missing Commit Validation",
            "statement": "Uncommitted state allowed corrupt payload to be read.",
            "category": "COMMIT_VALIDATION",
            "status": "UNTESTED",
            "evidence": ["Candidate explanation: Missing commit marker allowed corrupt payload."],
            "score": 0.3,
        })
    else:
        hypotheses.append({
            "id": "H1",
            "name": "General Invariant Violation",
            "statement": "Recovery exposed state violating formal invariants.",
            "category": "GENERAL_INVARIANT",
            "status": "UNTESTED",
            "evidence": ["Invariant failure observed."],
            "score": 0.5,
        })

    return hypotheses
