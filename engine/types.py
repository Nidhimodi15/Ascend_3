from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class WriteOperation:
    txn_id: str
    key: str
    value: str
    version: int
    old_value: str


@dataclass
class DiskSnapshot:
    wal: List[Dict[str, Any]]
    data_pages: Dict[str, Any]
    metadata_index: Dict[str, Any]
    checksums: Dict[str, str]
    commit_markers: Dict[str, Any]


@dataclass
class RecoveredRecord:
    key: str
    value: str
    version: int
    txn_id: str


@dataclass
class InvariantResult:
    invariant_id: str      # INV-1, INV-2, INV-3, INV-4
    name: str
    passed: bool
    expected: str
    actual: str
    details: str


@dataclass
class HookResult:
    hook: int
    phase: str             # LOG, DATA, META, COMMIT
    step_description: str
    disk_snapshot: DiskSnapshot
    recovered_records: List[RecoveredRecord]
    invariants: List[InvariantResult]
    verdict: str           # "SAFE" or "BUG" — dynamically assigned by invariant checker
    bug_details: Optional[str]
    prevention_suggestion: Optional[Dict[str, str]] = None



@dataclass
class VerificationReport:
    seed: int
    strategy: str          # "naive" or "safe"
    results: List[HookResult]
    total_safe: int        # Computed from actual invariant results — never hardcoded
    total_bugs: int        # Computed from actual invariant results — never hardcoded
    timestamp: str
