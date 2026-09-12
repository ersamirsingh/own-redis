"""PyRedis entry point."""

import asyncio
import logging
from pyredis.core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pyredis")


import uvicorn
from pyredis.api.app import create_app
from pyredis.commands.registry import registry
from pyredis.persistence.aof import AofEngine
from pyredis.persistence.snapshot import SnapshotEngine
from pyredis.server.tcp import TcpServer
from pyredis.storage.store import DataStore


async def main_async() -> None:
    """Initialize and run PyRedis TCP server and management API."""
    logger.info("Initializing PyRedis Engine...")

    store = DataStore()
    aof = AofEngine(
        filepath=settings.AOF_PATH,
        fsync_policy=settings.AOF_FSYNC_POLICY,
        enabled=settings.AOF_ENABLED,
    )
    snapshot = SnapshotEngine(
        filepath=settings.SNAPSHOT_PATH,
        enabled=settings.SNAPSHOT_ENABLED,
    )

    if settings.SNAPSHOT_ENABLED:
        try:
            snapshot.load(store)
        except Exception as e:
            logger.warning(f"Could not load snapshot: {e}")

    if settings.AOF_ENABLED:
        try:
            aof.replay(store, registry)
        except Exception as e:
            logger.warning(f"Could not replay AOF: {e}")

    aof.open()

    tcp_server = TcpServer(
        host=settings.HOST,
        port=settings.PORT,
        store=store,
        command_registry=registry,
        aof=aof,
        snapshot=snapshot,
    )
    await tcp_server.start()

    fastapi_app = create_app(store=store, aof=aof, snapshot=snapshot)
    config = uvicorn.Config(
        app=fastapi_app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        lifespan="on",
    )
    server = uvicorn.Server(config)

    logger.info(f"TCP server listening on {settings.HOST}:{settings.PORT}")
    logger.info(f"API server listening on {settings.API_HOST}:{settings.API_PORT}")
    logger.info("PyRedis ready to accept connections.")

    try:
        await server.serve()
    finally:
        await tcp_server.stop()
        aof.close()


def main() -> None:
    """CLI entry point."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
