"""Event types and event payload definitions for PyRedis Event Bus."""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class EventType(str, Enum):
    """Core domain event types emitted throughout the platform."""
    # Data mutations & lifecycle
    KEY_CREATED = "KEY_CREATED"
    KEY_UPDATED = "KEY_UPDATED"
    KEY_DELETED = "KEY_DELETED"
    KEY_EXPIRED = "KEY_EXPIRED"

    # Cache telemetry
    CACHE_HIT = "CACHE_HIT"
    CACHE_MISS = "CACHE_MISS"
    EVICTION = "EVICTION"

    # Persistence
    AOF_WRITE = "AOF_WRITE"
    SNAPSHOT_CREATED = "SNAPSHOT_CREATED"

    # Operational alerts
    SLOW_COMMAND = "SLOW_COMMAND"
    MEMORY_WARNING = "MEMORY_WARNING"
    NOTIFICATION = "NOTIFICATION"

    # Security & Auth
    AUTH_LOGIN = "AUTH_LOGIN"
    AUTH_LOGIN_FAILED = "AUTH_LOGIN_FAILED"
    AUTH_LOGOUT = "AUTH_LOGOUT"
    ROLE_CHANGED = "ROLE_CHANGED"
    API_KEY_CREATED = "API_KEY_CREATED"
    API_KEY_REVOKED = "API_KEY_REVOKED"


@dataclass
class Event:
    """Standardized event envelope published to the EventBus."""
    type: EventType
    timestamp: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    key: Optional[str] = None
    actor: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp,
            "key": self.key,
            "actor": self.actor,
            "metadata": self.metadata,
        }
