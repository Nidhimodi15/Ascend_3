"""
Crash Verifier — The Orchestrator.

Runs all 12 crash hooks identically:
  Fresh disk → [MySQL operation OR seeded operation] → Execute write → Crash → Recover → Check invariants → Report verdict

The verifier has ZERO hardcoded knowledge of which hooks will fail.
Verdicts are determined entirely by the invariant checker at runtime.

Two input paths (engine logic is identical for both):
  MYSQL PATH  — caller passes a WriteOperation fetched from MySQL directly.
  SEED PATH   — caller passes a seed; operation is generated via SeededRandom.
                Used only by Phase 1–3 tests for backward compatibility.
"""
from datetime import datetime
from typing import Optional

from engine.types import HookResult, VerificationReport, WriteOperation
from engine.seeded_random import generate_operation
from engine.simulated_disk import SimulatedDisk
from engine.storage_engine import execute_write, CrashInjected, HOOK_METADATA
from engine.naive_recovery import naive_recover
from engine.safe_recovery import safe_recover
from engine.invariant_checker import check_invariants
from app.security.prevention_rules import get_prevention_suggestion



def run_full_verification(
    seed: int,
    strategy: str,
    operation: Optional[WriteOperation] = None,
) -> VerificationReport:
    """
    Run the verification engine across all 12 crash hooks.

    For each hook N:
      1. Create a fresh simulated disk
      2. Use provided WriteOperation (MySQL path) OR generate from seed (test path)
      3. Execute the write path, injecting a crash at hook N
      4. Discard volatile buffers (simulate power loss)
      5. Snapshot the persisted disk state
      6. Run recovery (naive or safe)
      7. Run the invariant checker against the recovered state
      8. Record the verdict based solely on invariant results

    The verifier discovers whichever hooks violate the invariants at runtime.
    In the reference scenario, Hooks 09–11 demonstrate the naive vulnerability.

    Args:
        seed: Used ONLY when operation=None (Phase 1–3 test compatibility).
        strategy: "naive" or "safe" recovery.
        operation: WriteOperation from MySQL adapter (runtime MySQL path).
                   If None, falls back to generate_operation(seed) for tests.
    """
    results: list[HookResult] = []

    for hook_info in HOOK_METADATA:
        hook_num = hook_info["hook"]

        # 1. Fresh disk for every hook — no state bleeds across runs
        disk = SimulatedDisk()

        # 2. MySQL PATH: use actual operation from database.
        #    SEED PATH (tests only): generate deterministic operation from seed.
        op = operation if operation is not None else generate_operation(seed)

        # 3. Execute write with crash injection
        write_acknowledged = False
        try:
            execute_write(disk, op, crash_at=hook_num)
            # If we reach here, write completed before crash was triggered
            write_acknowledged = True
        except CrashInjected:
            # 4. Power loss — discard all volatile buffers
            disk.crash()

        # 5. Snapshot the persisted disk state (what survived the crash)
        snapshot = disk.snapshot()

        # 6. Run the selected recovery algorithm
        if strategy == "naive":
            recovered = naive_recover(disk)
        else:
            recovered = safe_recover(disk)

        # 7. Run invariant checker — THIS is where bugs are discovered
        invariants = check_invariants(
            recovered_records=recovered,
            operation=op,
            disk_snapshot=snapshot,
            write_was_acknowledged=write_acknowledged,
        )

        # 8. Verdict is determined entirely by the invariant checker results
        all_passed = all(inv.passed for inv in invariants)
        failed_invariants = [inv for inv in invariants if not inv.passed]

        results.append(HookResult(
            hook=hook_num,
            phase=hook_info["phase"],
            step_description=hook_info["step"],
            disk_snapshot=snapshot,
            recovered_records=recovered,
            invariants=invariants,
            verdict="SAFE" if all_passed else "BUG",
            bug_details=failed_invariants[0].details if failed_invariants else None,
            prevention_suggestion=get_prevention_suggestion(invariants, snapshot, recovered),
        ))


    # Count totals dynamically from actual results — never hardcoded
    total_bugs = sum(1 for r in results if r.verdict == "BUG")
    total_safe = sum(1 for r in results if r.verdict == "SAFE")

    return VerificationReport(
        seed=seed,
        strategy=strategy,
        results=results,
        total_safe=total_safe,
        total_bugs=total_bugs,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


def run_single_hook(
    seed: int,
    strategy: str,
    hook: int,
    operation: Optional[WriteOperation] = None,
) -> HookResult:
    """
    Run verification for a single hook only.
    Used by the reproduce endpoint to confirm deterministic failure.

    Args:
        operation: WriteOperation from MySQL (runtime path). If None, uses seed.
    """
    report = run_full_verification(seed=seed, strategy=strategy, operation=operation)
    return report.results[hook - 1]
