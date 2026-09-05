"""
fingerprint.py — Failure Fingerprint Generator.

Generates deterministic failure fingerprints from ACTUAL runtime evidence.
Combines persisted disk flags and invariant pass/fail statuses.
Zero hardcoded hook numbers.
"""
import hashlib
from typing import Dict, Any
from engine.types import HookResult


def create_failure_fingerprint(hook_result: HookResult) -> Dict[str, Any]:
    """
    Generate a structural failure fingerprint dictionary and hash from a HookResult.
    """
    snap = hook_result.disk_snapshot
    has_data = bool(snap and snap.data_pages and len(snap.data_pages) > 0)
    has_meta = bool(snap and snap.metadata_index and len(snap.metadata_index) > 0)
    has_csum = bool(snap and snap.checksums and len(snap.checksums) > 0)
    has_commit = bool(snap and snap.commit_markers and any(m.get("committed") for m in snap.commit_markers.values()))

    record_exposed = bool(hook_result.recovered_records and len(hook_result.recovered_records) > 0)

    # Invariant statuses
    inv_map = {inv.invariant_id: ("PASS" if inv.passed else "FAIL") for inv in hook_result.invariants}

    fp = {
        "data_present": has_data,
        "metadata_present": has_meta,
        "checksum_present": has_csum,
        "commit_present": has_commit,
        "record_exposed": record_exposed,
        "inv1": inv_map.get("INV-1", "PASS"),
        "inv2": inv_map.get("INV-2", "PASS"),
        "inv3": inv_map.get("INV-3", "PASS"),
        "inv4": inv_map.get("INV-4", "PASS"),
        "verdict": hook_result.verdict,
    }

    # Generate unique hash string for clustering failure families
    raw_str = f"d:{has_data}|m:{has_meta}|cs:{has_csum}|cm:{has_commit}|exp:{record_exposed}|i1:{fp['inv1']}|i2:{fp['inv2']}|i3:{fp['inv3']}|i4:{fp['inv4']}"
    fp["hash"] = hashlib.md5(raw_str.encode("utf-8")).hexdigest()[:10]
    fp["signature"] = f"DATA:{'✓' if has_data else '✕'}|META:{'✓' if has_meta else '✕'}|COMMIT:{'✓' if has_commit else '✕'}|EXP:{'✓' if record_exposed else '✕'}|INV3:{fp['inv3']}"

    return fp
