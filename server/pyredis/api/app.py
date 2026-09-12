"""FastAPI Management API application factory."""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pyredis.api.routes import (
    auth_router,
    commands_router,
    keys_router,
    locks_router,
    telemetry_router,
    websocket_router,
)
from pyredis.api.routes.keys import set_storage_reference
from pyredis.api.routes.telemetry import set_telemetry_references
from pyredis.api.websocket import ws_manager
from pyredis.core.config import settings
from pyredis.eviction.policy import EvictionManager
from pyredis.expiration.manager import ExpirationManager
from pyredis.metrics import metrics_collector
from pyredis.persistence.aof import AofEngine
from pyredis.persistence.snapshot import SnapshotEngine
from pyredis.storage.store import DataStore


def create_app(
    store: Optional[DataStore] = None,
    aof: Optional[AofEngine] = None,
    snapshot: Optional[SnapshotEngine] = None,
) -> FastAPI:
    """Create and configure FastAPI management application."""
    active_store = store if store is not None else DataStore()
    active_exp = ExpirationManager(active_store)
    active_evict = EvictionManager(active_store, max_memory=settings.MAX_MEMORY_BYTES, policy=settings.EVICTION_POLICY)
    active_aof = aof if aof is not None else AofEngine(filepath=settings.AOF_PATH, fsync_policy=settings.AOF_FSYNC_POLICY, enabled=settings.AOF_ENABLED)
    active_snap = snapshot if snapshot is not None else SnapshotEngine(filepath=settings.SNAPSHOT_PATH, enabled=settings.SNAPSHOT_ENABLED)

    set_storage_reference(active_store, active_evict)
    set_telemetry_references(active_exp, active_evict, active_aof, active_snap)
    ws_manager.setup_event_bridge()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Startup
        active_exp.start_worker()
        active_aof.start_background_fsync()
        ws_manager.setup_event_bridge()

        def _get_stats():
            summary = metrics_collector.get_summary()
            summary["memory_used_bytes"] = active_store.memory_usage()
            summary["total_keys"] = active_store.dbsize()
            return summary

        ws_manager.start_heartbeat(_get_stats, interval_seconds=1.0)
        yield
        # Shutdown
        await ws_manager.stop_heartbeat()
        await active_exp.stop_worker()
        await active_aof.stop_background_fsync()

    app = FastAPI(
        title="PyRedis Management API",
        description="RESTful Control Plane, Data Console, and Telemetry Gateway for PyRedis",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS for Next.js frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allows Next.js development server
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routers
    app.include_router(auth_router, prefix="/api")
    app.include_router(keys_router, prefix="/api")
    app.include_router(locks_router, prefix="/api")
    app.include_router(commands_router, prefix="/api")
    app.include_router(telemetry_router, prefix="/api")
    app.include_router(websocket_router)

    return app


# Default app instance
app = create_app()
