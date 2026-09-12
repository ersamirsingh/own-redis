"""Runner script for PyRedis engine and management API server."""

import asyncio
import logging
import sys
from pyredis.main import run

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logging.info("PyRedis shutdown requested by user.")
        sys.exit(0)
