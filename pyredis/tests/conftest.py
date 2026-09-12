"""Pytest configuration and fixtures."""

import pytest
from pyredis.core.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    """Fixture providing isolated test settings."""
    return Settings(
        PORT=16379,
        API_PORT=18000,
        AOF_ENABLED=False,
        SNAPSHOT_ENABLED=False,
        LOG_LEVEL="DEBUG",
    )
