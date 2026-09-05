"""
All API routes for the KillPoint verification engine & security layer.
"""
import dataclasses
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from engine.crash_verifier import run_full_verification, run_single_hook
from engine.storage_engine import HOOK_METADATA
from app.auth.manager import auth_manager, require_auth
from app.audit.logger import audit_logger
from app.security.encryption import encryptor

router = APIRouter()


# ─── Request schemas ──────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(description="Admin username")
    password: str = Field(description="Admin password")


class RunAllRequest(BaseModel):
    seed: int = Field(default=48291, ge=1, description="Seed for deterministic operation generation")
    strategy: str = Field(default="naive", pattern="^(naive|safe)$", description="Recovery strategy: naive or safe")


class CompareRequest(BaseModel):
    seed: int = Field(default=48291, ge=1)


class ReproduceRequest(BaseModel):
    seed: int = Field(ge=1)
    hook: int = Field(ge=1, le=12)
    strategy: str = Field(default="naive", pattern="^(naive|safe)$")


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
    Bugs are discovered dynamically by the invariant checker — never hardcoded.
    """
    report = run_full_verification(seed=request.seed, strategy=request.strategy)
    
    audit_logger.log(
        action="RUN_VERIFICATION",
        user=user,
        seed=request.seed,
        strategy=request.strategy,
        verdict=f"{report.total_safe} Safe / {report.total_bugs} Bugs",
        details=f"Executed 12-hook sweep for seed {request.seed} with strategy {request.strategy}",
    )
    
    return _to_dict(report)


@router.post("/compare")
async def compare(request: CompareRequest, user: str = Depends(require_auth)):
    """
    Run both naive and safe strategies with the same seed. Protected by authentication.
    """
    naive_report = run_full_verification(seed=request.seed, strategy="naive")
    safe_report  = run_full_verification(seed=request.seed, strategy="safe")
    
    audit_logger.log(
        action="COMPARE_STRATEGIES",
        user=user,
        seed=request.seed,
        details=f"Compared Naive ({naive_report.total_bugs} bugs) vs Safe ({safe_report.total_bugs} bugs) for seed {request.seed}",
    )
    
    return {
        "seed": request.seed,
        "naive": _to_dict(naive_report),
        "safe":  _to_dict(safe_report),
    }


@router.post("/reproduce")
async def reproduce(request: ReproduceRequest, user: str = Depends(require_auth)):
    """
    Deterministically reproduce a specific hook result. Protected by authentication.
    """
    hook_result = run_single_hook(
        seed=request.seed,
        strategy=request.strategy,
        hook=request.hook,
    )
    
    failed_inv = next((i.invariant_id for i in hook_result.invariants if not i.passed), None)
    
    audit_logger.log(
        action="REPRODUCE_BUG" if hook_result.verdict == "BUG" else "INSPECT_HOOK",
        user=user,
        seed=request.seed,
        strategy=request.strategy,
        hook=request.hook,
        verdict=hook_result.verdict,
        failed_invariant=failed_inv,
        details=f"Inspected Hook {request.hook} ({hook_result.verdict}) for seed {request.seed}",
    )
    
    return {
        "reproducible": True,
        "seed": request.seed,
        "hook": request.hook,
        "strategy": request.strategy,
        "result": _to_dict(hook_result),
    }


@router.post("/run-hook/{hook_num}")
async def run_single(hook_num: int, request: RunAllRequest, user: str = Depends(require_auth)):
    """Run verification for a single specific hook number. Protected by authentication."""
    if hook_num < 1 or hook_num > 12:
        raise HTTPException(status_code=400, detail="Hook must be between 1 and 12")
    hook_result = run_single_hook(
        seed=request.seed,
        strategy=request.strategy,
        hook=hook_num,
    )
    return _to_dict(hook_result)


# ─── Agent Investigation Endpoints ──────────────────────────────────────────

from typing import Optional
from app.agent.agent import AutonomousInvestigationAgent

INVESTIGATION_STORE = {}


class AgentInvestigateRequest(BaseModel):
    seed: int = Field(default=48291, ge=1)
    strategy: str = Field(default="naive", pattern="^(naive|safe)$")
    initial_hook: Optional[int] = Field(default=None, ge=1, le=12)


@router.post("/agent/investigate")
async def agent_investigate(request: AgentInvestigateRequest, user: str = Depends(require_auth)):
    """
    Run the Autonomous Root-Cause Investigator Agent. Protected by authentication.
    """
    agent = AutonomousInvestigationAgent(max_experiments=20)
    report = agent.investigate(seed=request.seed, strategy=request.strategy, initial_hook=request.initial_hook)
    
    INVESTIGATION_STORE[report["investigation_id"]] = report

    audit_logger.log(
        action="AGENT_INVESTIGATE",
        user=user,
        seed=request.seed,
        strategy=request.strategy,
        verdict=report["status"],
        details=f"Agent completed investigation ({report['confidence']} confidence): {report['root_cause']}",
    )

    return report


@router.get("/agent/investigation/{inv_id}")
async def get_investigation(inv_id: str, user: str = Depends(require_auth)):
    """Retrieve an agent investigation report by ID."""
    report = INVESTIGATION_STORE.get(inv_id)
    if not report:
        raise HTTPException(status_code=404, detail="Investigation ID not found")
    return report

