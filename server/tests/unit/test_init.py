"""Initial sanity test for PyRedis imports and configuration."""

from pyredis import __version__
from pyredis.core.config import settings
from pyredis.core.types import DataType, Role, FsyncPolicy, EvictionPolicy


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_core_types() -> None:
    assert DataType.STRING == "string"
    assert Role.ADMIN == "admin"
    assert Role.DEVELOPER == "developer"
    assert FsyncPolicy.EVERYSEC == "everysec"
    assert EvictionPolicy.ADAPTIVE == "adaptive"


def test_settings_load(test_settings) -> None:
    assert test_settings.PORT == 16379
    assert test_settings.AOF_ENABLED is False
    assert settings.PORT == 6379
