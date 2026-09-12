"""Audit logging for tracking administrative and data operations."""

import time
from typing import Any, Dict, List, Optional
from pyredis.auth.models import AuditLogEntry
from pyredis.core.types import Role
from pyredis.events import Event, EventType, event_bus


class AuditLogger:
    """Records security and data modification events for compliance and review."""

    def __init__(self, max_entries: int = 1000) -> None:
        self.max_entries: int = max_entries
        self._entries: List[AuditLogEntry] = []

    def log(
        self,
        actor_id: str,
        actor_email: str,
        actor_role: Role,
        action: str,
        target: Optional[str] = None,
        outcome: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntry:
        """Create and store audit log record and emit domain event."""
        entry = AuditLogEntry(
            actor_id=actor_id,
            actor_email=actor_email,
            actor_role=actor_role,
            action=action,
            target=target,
            outcome=outcome,
            details=details or {},
        )
        self._entries.append(entry)
        if len(self._entries) > self.max_entries:
            self._entries.pop(0)

        # Emit audit event to EventBus
        event_bus.publish(Event(
            type=EventType.KEY_UPDATED if "KEY" in action else EventType.AUTH_LOGIN,
            key=target,
            actor=actor_email,
            metadata={"action": action, "outcome": outcome, "details": details or {}},
        ))

        return entry

    def list_entries(
        self,
        limit: int = 50,
        action: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Filter and retrieve audit entries for Admin audit console."""
        matches = []
        for e in reversed(self._entries):
            if action and action.upper() not in e.action.upper():
                continue
            if actor and actor.lower() not in e.actor_email.lower():
                continue
            matches.append(e.model_dump())
            if len(matches) >= limit:
                break
        return matches

    def clear(self) -> None:
        self._entries.clear()


# Global audit logger singleton
audit_logger = AuditLogger()
