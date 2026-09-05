"""
Rule-Based Automatic Prevention Suggestion Engine.

Generates actionable prevention recommendations based ENTIRELY on actual runtime
invariant failures and persisted disk state. ZERO hardcoded hook numbers.
"""
from typing import Optional, List, Dict, Any
from engine.types import InvariantResult, DiskSnapshot, RecoveredRecord


def get_prevention_suggestion(
    invariants: List[InvariantResult],
    snapshot: Optional[DiskSnapshot] = None,
    recovered_records: Optional[List[RecoveredRecord]] = None,
) -> Optional[Dict[str, str]]:
    """
    Dynamically analyze failed invariants and disk state to generate prevention suggestions.

    Returns None if all invariants passed (SAFE hook).
    Returns a dictionary with 'problem', 'rule', and 'action' if invariants failed (BUG hook).
    """
    failed_invariants = [inv for inv in invariants if not inv.passed]
    
    # If no invariants failed, this is a SAFE hook — no prevention suggestion needed
    if not failed_invariants:
        return None

    # Inspect disk snapshot structure if available
    has_data = bool(snapshot and snapshot.data_pages and len(snapshot.data_pages) > 0)
    has_meta = bool(snapshot and snapshot.metadata_index and len(snapshot.metadata_index) > 0)
    has_csum = bool(snapshot and snapshot.checksums and len(snapshot.checksums) > 0)
    has_commit = bool(snapshot and snapshot.commit_markers and len(snapshot.commit_markers) > 0)

    for failed in failed_invariants:
        inv_id = failed.invariant_id
        details_lower = (failed.details or "").lower()

        # Rule 1: INV-3 failure (Commit marker missing/invalid for exposed record)
        if inv_id == "INV-3" or "commit marker" in details_lower or ("uncommitted" in details_lower and not has_commit):
            return {
                "problem": "Commit marker is missing.",
                "rule": "Never expose a recovered record unless the Commit Marker is VALID.",
                "action": "ROLL BACK / HIDE RECORD",
            }

        # Rule 2: INV-4 failure (Checksum missing/invalid)
        if inv_id == "INV-4" or "checksum" in details_lower or not has_csum:
            return {
                "problem": "Record checksum verification failed or is missing.",
                "rule": "Reject the record unless checksum verification succeeds.",
                "action": "REJECT RECORD",
            }

        # Rule 3: Metadata missing or invalid
        if "metadata" in details_lower or (has_data and not has_meta):
            return {
                "problem": "Record metadata is missing or invalid.",
                "rule": "Do not expose the record unless valid metadata exists.",
                "action": "ROLL BACK / HIDE RECORD",
            }

        # Rule 4: Data payload incomplete or invalid
        if "payload" in details_lower or "corrupt" in details_lower or "incomplete" in details_lower:
            return {
                "problem": "Data payload is incomplete or invalid.",
                "rule": "Reject incomplete data and recover the last valid record.",
                "action": "RECOVER LAST VALID RECORD",
            }

        # Rule 5: INV-2 failure (Acknowledged write missing)
        if inv_id == "INV-2" or "acknowledged" in details_lower:
            return {
                "problem": "Acknowledged write is missing from recovered state.",
                "rule": "Recover the last durable acknowledged version before exposing the record.",
                "action": "RECOVER LAST VALID VERSION",
            }

    # Rule 6: Fallback for unclassified BUG hooks
    return {
        "problem": "Invariant check failed.",
        "rule": "No automatic prevention rule available for this failure.",
        "action": "MANUAL INSPECTION REQUIRED",
    }
