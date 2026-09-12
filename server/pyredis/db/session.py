"""Asynchronous database engine and session factory supporting PostgreSQL and SQLite."""

import logging
import os
from pathlib import Path
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from pyredis.core.config import settings
from pyredis.db.models import Base

logger = logging.getLogger("pyredis.db")

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_database_url() -> str:
    """Resolve database URL with asyncpg/aiosqlite driver prefix."""
    raw_url = settings.DATABASE_URL or os.getenv("DATABASE_URL")
    if raw_url:
        # Normalize postgres URLs to asyncpg
        if raw_url.startswith("postgresql://"):
            return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if raw_url.startswith("postgres://"):
            return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
        return raw_url

    # Fallback to local SQLite for tests and offline standalone mode
    data_dir = Path("./data")
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "pyredis_control.db"
    return f"sqlite+aiosqlite:///{db_path.as_posix()}"


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = get_database_url()
        is_sqlite = url.startswith("sqlite")
        connect_args = {"check_same_thread": False} if is_sqlite else {}
        _engine = create_async_engine(
            url,
            echo=False,
            future=True,
            connect_args=connect_args,
        )
        logger.info("Initialized database engine with URL type: %s", url.split("://")[0])
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def init_db() -> None:
    """Initialize database tables idempotently."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency helper yielding an active database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
