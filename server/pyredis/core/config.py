"""Configuration management for PyRedis using Pydantic Settings."""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pyredis.core.types import FsyncPolicy, EvictionPolicy


class Settings(BaseSettings):
    """PyRedis configuration settings loaded from environment or .env file."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # TCP Server
    PORT: int = 6379
    HOST: str = "0.0.0.0"

    # HTTP API
    API_PORT: int = 8000
    API_HOST: str = "0.0.0.0"

    # Authentication & Security
    JWT_SECRET: str = "supersecret-pyredis-production-key-change-in-prod-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DATABASE_URL: Optional[str] = None

    # AI Configuration (Gemini)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"

    # Memory & Eviction
    MAX_MEMORY_BYTES: int = 256 * 1024 * 1024  # 256 MB default
    EVICTION_POLICY: EvictionPolicy = EvictionPolicy.NOEVICTION

    # Persistence
    AOF_ENABLED: bool = True
    AOF_FSYNC_POLICY: FsyncPolicy = FsyncPolicy.EVERYSEC
    AOF_PATH: str = "./data/appendonly.aof"
    SNAPSHOT_ENABLED: bool = True
    SNAPSHOT_INTERVAL_SEC: int = 300
    SNAPSHOT_PATH: str = "./data/dump.rdb"

    # Observability
    LOG_LEVEL: str = "INFO"
    SLOW_QUERY_THRESHOLD_MS: float = 5.0


settings = Settings()
