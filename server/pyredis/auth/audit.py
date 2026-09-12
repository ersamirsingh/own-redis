"""Audit logging for tracking administrative and data operations backed by PostgreSQL / SQLite."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from pyredis.auth.models import AuditLogEntry
from pyredis.core.types import Role
from pyredis.db.models import AuditLogModel
from pyredis.db.session import get_session_factory
from pyredis.events import Event, EventType, event_bus

logger = logging.getLogger("pyredis.auth.audit")


def _safe_schedule(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        coro.close()


class AuditLogger:
    """Records security and data modification events for compliance and review."""

    def __init__(self, max_entries: int = 1000) -> None:
        self.max_entries: int = max_entries
        self._entries: List[AuditLogEntry] = []

    async def _persist_audit_log(self, entry: AuditLogEntry) -> None:
        try:
            factory = get_session_factory()
            async with factory() as session:
                db_entry = AuditLogModel(
                    id=entry.id,
                    actor_id=entry.actor_id,
                    actor_email=entry.actor_email,
                    actor_role=entry.actor_role.value if isinstance(entry.actor_role, Role) else str(entry.actor_role),
                    action=entry.action,
                    target=entry.target,
                    outcome=entry.outcome,
                    details=json.dumps(entry.details) if entry.details else None,
                    timestamp=entry.timestamp,
                )
                session.add(db_entry)
                await session.commit()
        except Exception as e:
            logger.debug("Failed to persist audit entry to DB: %s", e)

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
        """Create and store audit log record, persist to DB, and emit domain event."""
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

        _safe_schedule(self._persist_audit_log(entry))

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
        """Filter and retrieve audit entries from in-memory cache."""
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

    async def list_entries_async(
        self,
        limit: int = 50,
        action: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query persistent audit log table with in-memory fallback."""
        try:
            factory = get_session_factory()
            async with factory() as session:
                stmt = select(AuditLogModel).order_by(AuditLogModel.timestamp.desc())
                if action:
                    stmt = stmt.where(AuditLogModel.action.ilike(f"%{action}%"))
                if actor:
                    stmt = stmt.where(AuditLogModel.actor_email.ilike(f"%{actor}%"))
                stmt = stmt.limit(limit)
                res = await session.execute(stmt)
                records = res.scalars().all()
                if records:
                    return [r.to_dict() for r in records]
        except Exception as e:
            logger.debug("Database audit query failed, falling back to cache: %s", e)

        return self.list_entries(limit=limit, action=action, actor=actor)

    def clear(self) -> None:
        self._entries.clear()


# Global audit logger singleton
audit_logger = AuditLogger()

