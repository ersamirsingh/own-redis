"""API routes package."""

from pyredis.api.routes.auth import router as auth_router
from pyredis.api.routes.commands import router as commands_router
from pyredis.api.routes.keys import router as keys_router
from pyredis.api.routes.locks import router as locks_router
from pyredis.api.routes.telemetry import router as telemetry_router
from pyredis.api.routes.websocket import router as websocket_router

__all__ = [
    "auth_router",
    "keys_router",
    "commands_router",
    "telemetry_router",
    "websocket_router",
    "locks_router",
]
