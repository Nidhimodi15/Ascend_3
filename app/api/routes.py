"""
All API routes for the KillPoint verification engine & security layer.
"""
import dataclasses
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from engine.crash_verifier import run_full_verification, run_single_hook
from engine.storage_engine import HOOK_METADATA
from app.auth.manager import auth_manager, require_auth
from app.audit.logger import audit_logger
from app.security.encryption import encryptor
from app.adapters.mysql_adapter import (
    test_connection,
    fetch_transactions,
    fetch_transaction,
    convert_to_write_operation,
)

router = APIRouter()


# ─── Request schemas ──────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(description="Admin username")
    password: str = Field(description="Admin password")


class RunAllRequest(BaseModel):
    txn_id:   Optional[str] = Field(default=None, description="MySQL transaction ID (e.g. T101). If provided, fetches actual transaction data from MySQL.")
    seed:     int            = Field(default=48291, ge=1, description="Seed for deterministic operation (used only when txn_id is not provided — Phase 1–3 test compatibility)")
    strategy: str            = Field(default="naive", pattern="^(naive|safe)$", description="Recovery strategy: naive or safe")


class CompareRequest(BaseModel):
    txn_id: Optional[str] = Field(default=None, description="MySQL transaction ID for comparison")
    seed:   int            = Field(default=48291, ge=1)


class ReproduceRequest(BaseModel):
    txn_id:   Optional[str] = Field(default=None, description="MySQL transaction ID to reproduce")
    seed:     int            = Field(default=48291, ge=1)
    hook:     int            = Field(ge=1, le=12)
    strategy: str            = Field(default="naive", pattern="^(naive|safe)$")


# ─── Serialization helper ─────────────────────────────────────────────────────

def _to_dict(obj):
    """Recursively convert dataclasses to dicts for JSON serialization."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


def _resolve_operation(txn_id: Optional[str], seed: int):
    """
    Resolve the WriteOperation to use for verification.

    MYSQL PATH  (preferred / runtime):
        If txn_id is provided, fetch the actual MySQL record and convert it
        directly to a WriteOperation. SeededRandom is NOT called.

    SEED PATH (test compatibility only):
        If txn_id is None, fall back to seed-based generation.
        Used only by Phase 1–3 tests.

    Returns:
        (operation_or_None, effective_seed)
        When MySQL path is used: (WriteOperation, 0)
        When seed path is used:  (None, seed)
    """
    if txn_id:
        row = fetch_transaction(txn_id)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Transaction '{txn_id}' not found in MySQL database. Run: python scripts/seed_mysql.py"
            )
        operation = convert_to_write_operation(row)
        return operation, 0  # seed unused in MySQL path
    return None, seed  # seed path for tests


# ─── Public Endpoints ─────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "KillPoint Verifier",
        "security": "Production-Inspired",
        "encryption": encryptor.algorithm,
    }


@router.get("/hooks")
async def get_hooks():
    """Return metadata for all 12 crash hooks."""
    return {"hooks": HOOK_METADATA}


# ─── MySQL Status Endpoints (public) ─────────────────────────────────────────

@router.get("/mysql/status")
async def mysql_status():
    """
    Return real-time MySQL connection status and transaction count.
    Public endpoint — no authentication required.
    Shows whether the KillPoint database is connected and seeded.
    """
    status = test_connection()
    return status


@router.get("/mysql/transactions")
async def mysql_transactions():
    """
    Return all transactions stored in the MySQL `killpoint` database.
    Public endpoint — no authentication required.
    These are the actual records that drive the verification engine.
    """
    rows = fetch_transactions()
    return {
        "count"        : len(rows),
        "transactions" : rows,
    }


# ─── Auth Endpoints ───────────────────────────────────────────────────────────

@router.post("/auth/login")
async def login(request: LoginRequest):
    """Authenticate user and return session token."""
    token = auth_manager.authenticate(request.username, request.password)
    if not token:
        audit_logger.log(
            action="LOGIN_FAILED",
            user=request.username,
            details=f"Failed login attempt for user '{request.username}'",
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )
    
    audit_logger.log(
        action="LOGIN_SUCCESS",
        user=request.username,
        details=f"User '{request.username}' logged in successfully",
    )
    return {
        "authenticated": True,
        "token": token,
        "username": request.username,
    }


@router.get("/auth/status")
async def auth_status():
    """Return authentication and security status."""
    return {
        "encryption": {
            "enabled": True,
            "algorithm": encryptor.algorithm,
        },
        "audit_logging": {
            "enabled": True,
            "total_events": len(audit_logger.get_events(limit=500)),
        },
    }


# ─── Protected Security & Audit Endpoints ─────────────────────────────────────

@router.get("/security/audit-logs")
async def get_audit_logs(user: str = Depends(require_auth)):
    """Return recent security audit logs."""
    return {
        "audit_stats": audit_logger.get_stats(),
        "events": audit_logger.get_events(limit=50),
    }


# ─── Protected Verification Endpoints ─────────────────────────────────────────

@router.post("/run-all")
async def run_all(request: RunAllRequest, user: str = Depends(require_auth)):
    """
    Run the full 12-hook verification sweep. Protected by authentication.

    MYSQL PATH  (runtime): Send {"txn_id": "T101", "strategy": "naive"}
                           Backend fetches T101 from MySQL → WriteOperation → engine.

    SEED PATH   (tests):   Send {"seed": 48291, "strategy": "naive"}
                           Backend generates operation via SeededRandom (test compat only).

    Bugs are discovered dynamically by the invariant checker — never hardcoded.
    """
    operation, effective_seed = _resolve_operation(request.txn_id, request.seed)

    report = run_full_verification(
        seed=effective_seed,
        strategy=request.strategy,
        operation=operation,
    )

    data_source = f"MySQL:{request.txn_id}" if request.txn_id else f"seed:{request.seed}"
    audit_logger.log(
        action="RUN_VERIFICATION",
        user=user,
        seed=effective_seed,
        strategy=request.strategy,
        verdict=f"{report.total_safe} Safe / {report.total_bugs} Bugs",
        details=f"Executed 12-hook sweep [{data_source}] with strategy {request.strategy}",
    )

    return _to_dict(report)


@router.post("/compare")
async def compare(request: CompareRequest, user: str = Depends(require_auth)):
    """
    Run both naive and safe strategies with the same transaction. Protected by authentication.
    """
    operation, effective_seed = _resolve_operation(request.txn_id, request.seed)

    naive_report = run_full_verification(seed=effective_seed, strategy="naive", operation=operation)
    safe_report  = run_full_verification(seed=effective_seed, strategy="safe",  operation=operation)

    data_source = f"MySQL:{request.txn_id}" if request.txn_id else f"seed:{request.seed}"
    audit_logger.log(
        action="COMPARE_STRATEGIES",
        user=user,
        seed=effective_seed,
        details=f"Compared Naive ({naive_report.total_bugs} bugs) vs Safe ({safe_report.total_bugs} bugs) [{data_source}]",
    )

    return {
        "txn_id": request.txn_id,
        "seed"  : effective_seed,
        "naive" : _to_dict(naive_report),
        "safe"  : _to_dict(safe_report),
    }


@router.post("/reproduce")
async def reproduce(request: ReproduceRequest, user: str = Depends(require_auth)):
    """
    Deterministically reproduce a specific hook result. Protected by authentication.
    """
    operation, effective_seed = _resolve_operation(request.txn_id, request.seed)

    hook_result = run_single_hook(
        seed=effective_seed,
        strategy=request.strategy,
        hook=request.hook,
        operation=operation,
    )

    failed_inv = next((i.invariant_id for i in hook_result.invariants if not i.passed), None)

    data_source = f"MySQL:{request.txn_id}" if request.txn_id else f"seed:{request.seed}"
    audit_logger.log(
        action="REPRODUCE_BUG" if hook_result.verdict == "BUG" else "INSPECT_HOOK",
        user=user,
        seed=effective_seed,
        strategy=request.strategy,
        hook=request.hook,
        verdict=hook_result.verdict,
        failed_invariant=failed_inv,
        details=f"Inspected Hook {request.hook} ({hook_result.verdict}) [{data_source}]",
    )

    return {
        "reproducible": True,
        "txn_id"      : request.txn_id,
        "seed"        : effective_seed,
        "hook"        : request.hook,
        "strategy"    : request.strategy,
        "result"      : _to_dict(hook_result),
    }


@router.post("/run-hook/{hook_num}")
async def run_single(hook_num: int, request: RunAllRequest, user: str = Depends(require_auth)):
    """Run verification for a single specific hook number. Protected by authentication."""
    if hook_num < 1 or hook_num > 12:
        raise HTTPException(status_code=400, detail="Hook must be between 1 and 12")

    operation, effective_seed = _resolve_operation(request.txn_id, request.seed)

    hook_result = run_single_hook(
        seed=effective_seed,
        strategy=request.strategy,
        hook=hook_num,
        operation=operation,
    )
    return _to_dict(hook_result)


# ─── Agent Investigation Endpoints ──────────────────────────────────────────

from app.agent.agent import AutonomousInvestigationAgent

INVESTIGATION_STORE = {}


class AgentInvestigateRequest(BaseModel):
    txn_id:       Optional[str] = Field(default=None, description="MySQL transaction ID for investigation")
    seed:         int            = Field(default=48291, ge=1)
    strategy:     str            = Field(default="naive", pattern="^(naive|safe)$")
    initial_hook: Optional[int]  = Field(default=None, ge=1, le=12)


@router.post("/agent/investigate")
async def agent_investigate(request: AgentInvestigateRequest, user: str = Depends(require_auth)):
    """
    Run the Autonomous Root-Cause Investigator Agent. Protected by authentication.
    Uses MySQL transaction if txn_id is provided; falls back to seed for tests.
    """
    operation, effective_seed = _resolve_operation(request.txn_id, request.seed)

    agent  = AutonomousInvestigationAgent(max_experiments=20)
    report = agent.investigate(
        seed=effective_seed,
        strategy=request.strategy,
        initial_hook=request.initial_hook,
        operation=operation,
    )

    INVESTIGATION_STORE[report["investigation_id"]] = report

    data_source = f"MySQL:{request.txn_id}" if request.txn_id else f"seed:{request.seed}"
    audit_logger.log(
        action="AGENT_INVESTIGATE",
        user=user,
        seed=effective_seed,
        strategy=request.strategy,
        verdict=report["status"],
        details=f"Agent completed investigation [{data_source}]: {report['root_cause']}",
    )

    return report


@router.get("/agent/investigation/{inv_id}")
async def get_investigation(inv_id: str, user: str = Depends(require_auth)):
    """Retrieve an agent investigation report by ID."""
    report = INVESTIGATION_STORE.get(inv_id)
    if not report:
        raise HTTPException(status_code=404, detail="Investigation ID not found")
    return report
