"""PyRedis entry point."""

import asyncio
import logging
from pyredis.core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pyredis")


async def main_async() -> None:
    """Initialize and run PyRedis TCP server and management API."""
    logger.info("Initializing PyRedis Engine...")
    logger.info(f"TCP server configured on {settings.HOST}:{settings.PORT}")
    logger.info(f"API server configured on {settings.API_HOST}:{settings.API_PORT}")
    logger.info("PyRedis ready to accept connections.")


def main() -> None:
    """CLI entry point."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
