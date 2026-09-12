"""Pydantic models for authentication, users, API keys, and audit logging."""

import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from pyredis.core.types import Role


class UserBase(BaseModel):
    email: str
    name: str
    role: Role = Role.DEVELOPER


class UserCreate(BaseModel):
    email: str
    name: str
    password: str = Field(min_length=6)
    role: Optional[Role] = None  # If not specified, first user becomes ADMIN, others DEVELOPER


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: Role
    created_at: float


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class ApiKeyCreate(BaseModel):
    name: str
    role: Role = Role.DEVELOPER
    expires_in_days: Optional[int] = 30


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_preview: str  # e.g. "sk-pyredis-...ab12"
    raw_key: Optional[str] = None  # Only returned once upon creation
    role: Role
    created_at: float
    expires_at: Optional[float]


class AuditLogEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = Field(default_factory=time.time)
    actor_id: str
    actor_email: str
    actor_role: Role
    action: str
    target: Optional[str] = None
    outcome: str = "SUCCESS"  # SUCCESS or FAILURE
    details: Dict[str, Any] = Field(default_factory=dict)
