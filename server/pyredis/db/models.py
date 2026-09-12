"""SQLAlchemy ORM models for PyRedis Control Plane."""

import time
import uuid
from typing import Any, Dict, Optional
from sqlalchemy import Column, Float, ForeignKey, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class UserModel(Base):
    """User account model supporting multi-admin and developer roles."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, default="developer")
    created_at = Column(Float, nullable=False, default=time.time)
    updated_at = Column(Float, nullable=False, default=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ApiKeyModel(Base):
    """Scoped API key model for programmatic access."""
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    raw_key = Column(String(255), nullable=False, index=True)
    preview = Column(String(32), nullable=False)
    role = Column(String(32), nullable=False, default="developer")
    created_at = Column(Float, nullable=False, default=time.time)
    expires_at = Column(Float, nullable=True)

    def to_dict(self, include_raw: bool = False) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "key_preview": self.preview,
            "raw_key": self.raw_key if include_raw else None,
            "role": self.role,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


class AuditLogModel(Base):
    """Security and compliance audit trail model."""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id = Column(String(64), nullable=False)
    actor_email = Column(String(255), nullable=False)
    actor_role = Column(String(32), nullable=False)
    action = Column(String(64), nullable=False)
    target = Column(String(255), nullable=True)
    outcome = Column(String(32), nullable=False)
    details = Column(Text, nullable=True)  # JSON-encoded string
    timestamp = Column(Float, nullable=False, default=time.time)

    def to_dict(self) -> Dict[str, Any]:
        import json
        det = None
        if self.details:
            try:
                det = json.loads(self.details)
            except Exception:
                det = {"raw": self.details}
        return {
            "id": self.id,
            "actor_id": self.actor_id,
            "actor_email": self.actor_email,
            "actor_role": self.actor_role,
            "action": self.action,
            "target": self.target,
            "outcome": self.outcome,
            "details": det,
            "timestamp": self.timestamp,
        }


class PlatformSettingModel(Base):
    """Persistent platform settings."""
    __tablename__ = "platform_settings"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(Float, nullable=False, default=time.time)
