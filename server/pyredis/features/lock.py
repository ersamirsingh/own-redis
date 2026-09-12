"""Distributed locking subsystem with owner verification, lease timeouts, and reentrancy."""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from pyredis.events.bus import event_bus
from pyredis.events.types import Event, EventType

logger = logging.getLogger("pyredis.lock")


@dataclass
class LockInfo:
    """Active lock state and metadata."""
    key: str
    owner: str
    acquired_at: float
    expires_at: float

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def ttl_remaining_ms(self) -> int:
        remaining = self.expires_at - time.time()
        return max(0, int(remaining * 1000))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "owner": self.owner,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "ttl_remaining_ms": self.ttl_remaining_ms(),
        }


class LockManager:
    """Manages distributed locks with lease expiration and owner token verification."""

    def __init__(self) -> None:
        self._locks: Dict[str, LockInfo] = {}

    def _cleanup_if_expired(self, key: str) -> None:
        lock = self._locks.get(key)
        if lock and lock.is_expired():
            del self._locks[key]

    def acquire(self, key: str, owner: str, ttl_ms: int = 30000) -> bool:
        """Acquire lock on key. Returns True if acquired, False if locked by another owner."""
        now = time.time()
        self._cleanup_if_expired(key)

        existing = self._locks.get(key)
        if existing:
            # Re-entrant: if same owner, refresh lease
            if existing.owner == owner:
                existing.expires_at = now + (ttl_ms / 1000.0)
                return True
            return False

        expires_at = now + (ttl_ms / 1000.0)
        self._locks[key] = LockInfo(
            key=key,
            owner=owner,
            acquired_at=now,
            expires_at=expires_at,
        )

        event_bus.publish(Event(
            type=EventType.NOTIFICATION,
            key=key,
            actor=owner,
            metadata={"action": "LOCK_ACQUIRED", "ttl_ms": ttl_ms},
        ))
        return True

    def release(self, key: str, owner: str) -> bool:
        """Release lock if owner matches. Returns True if released, False otherwise."""
        self._cleanup_if_expired(key)
        existing = self._locks.get(key)
        if not existing:
            return False

        if existing.owner != owner:
            return False

        del self._locks[key]
        event_bus.publish(Event(
            type=EventType.NOTIFICATION,
            key=key,
            actor=owner,
            metadata={"action": "LOCK_RELEASED"},
        ))
        return True

    def extend(self, key: str, owner: str, ttl_ms: int) -> bool:
        """Extend active lock lease if owner matches."""
        self._cleanup_if_expired(key)
        existing = self._locks.get(key)
        if not existing or existing.owner != owner:
            return False

        existing.expires_at = time.time() + (ttl_ms / 1000.0)
        return True

    def info(self, key: str) -> Optional[Dict[str, Any]]:
        """Get information about an active lock on key."""
        self._cleanup_if_expired(key)
        lock = self._locks.get(key)
        if lock:
            return lock.to_dict()
        return None

    def list_locks(self) -> List[Dict[str, Any]]:
        """List all active unexpired locks."""
        now = time.time()
        # Clean expired
        expired = [k for k, v in self._locks.items() if v.expires_at <= now]
        for k in expired:
            del self._locks[k]

        return [v.to_dict() for v in self._locks.values()]

    def force_release(self, key: str) -> bool:
        """Administrative release of lock without owner validation."""
        if key in self._locks:
            del self._locks[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all active locks (for testing)."""
        self._locks.clear()


# Global LockManager singleton
lock_manager = LockManager()
