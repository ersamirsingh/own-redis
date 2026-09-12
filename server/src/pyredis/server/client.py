"""Client connection state tracking."""

import time
import uuid
from typing import Optional, Tuple
from pyredis.core.types import Role


class ClientConnection:
    """Represents an active client TCP connection."""

    def __init__(self, addr: Tuple[str, int]) -> None:
        self.id: str = str(uuid.uuid4())[:8]
        self.addr: Tuple[str, int] = addr
        self.connected_at: float = time.time()
        self.last_active_at: float = self.connected_at
        self.role: Role = Role.ADMIN  # Standard TCP connections default to Admin privileges
        self.authenticated: bool = True
        self.name: Optional[str] = None
        self.commands_executed: int = 0

    def touch(self) -> None:
        self.last_active_at = time.time()
        self.commands_executed += 1

    @property
    def peer(self) -> str:
        return f"{self.addr[0]}:{self.addr[1]}"
