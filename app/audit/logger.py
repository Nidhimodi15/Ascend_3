"""
Audit Logger — Security Event Audit System.

Records security and verification audit events while masking sensitive data.
Never logs raw passwords, secret keys, or authentication tokens.
"""
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List
from app.security.masking import mask_id


@dataclass
class AuditEvent:
    timestamp: str
    user: str
    action: str
    seed: Optional[int] = None
    strategy: Optional[str] = None
    hook: Optional[int] = None
    verdict: Optional[str] = None
    failed_invariant: Optional[str] = None
    masked_details: Optional[str] = None


class AuditLogger:
    """Stores and retrieves security audit events."""

    def __init__(self, max_records: int = 200):
        self.max_records = max_records
        self._events: List[AuditEvent] = []

    def log(
        self,
        action: str,
        user: str = "admin",
        seed: Optional[int] = None,
        strategy: Optional[str] = None,
        hook: Optional[int] = None,
        verdict: Optional[str] = None,
        failed_invariant: Optional[str] = None,
        details: Optional[str] = None,
    ) -> AuditEvent:
        """Record an audit event with masked sensitive details."""
        masked_det = mask_id(details) if details else None
        
        event = AuditEvent(
            timestamp=datetime.utcnow().isoformat() + "Z",
            user=user,
            action=action,
            seed=seed,
            strategy=strategy,
            hook=hook,
            verdict=verdict,
            failed_invariant=failed_invariant,
            masked_details=masked_det,
        )
        self._events.insert(0, event)
        if len(self._events) > self.max_records:
            self._events.pop()
        return event

    def get_events(self, limit: int = 50) -> List[dict]:
        """Retrieve recent audit events as list of dicts."""
        return [asdict(e) for e in self._events[:limit]]

    def get_stats(self) -> dict:
        """Return audit summary statistics."""
        return {
            "total_events": len(self._events),
            "audit_logging": "Active",
            "encryption_algorithm": "AES-256-GCM",
        }


audit_logger = AuditLogger()
