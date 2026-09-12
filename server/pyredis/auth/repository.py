"""User and API Key Repository backed by PostgreSQL / SQLite with in-memory caching."""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional
from sqlalchemy import select
from pyredis.auth.models import ApiKeyResponse, UserCreate, UserResponse
from pyredis.auth.security import generate_api_key, hash_password
from pyredis.core.types import Role
from pyredis.db.models import ApiKeyModel, UserModel
from pyredis.db.session import get_session_factory

logger = logging.getLogger("pyredis.auth.repository")


class StoredUser:
    def __init__(self, id: str, email: str, name: str, password_hash: str, role: Role) -> None:
        self.id: str = id
        self.email: str = email
        self.name: str = name
        self.password_hash: str = password_hash
        self.role: Role = role
        self.created_at: float = time.time()

    def to_response(self) -> UserResponse:
        return UserResponse(
            id=self.id,
            email=self.email,
            name=self.name,
            role=self.role,
            created_at=self.created_at,
        )


class StoredApiKey:
    def __init__(
        self,
        id: str,
        user_id: str,
        name: str,
        raw_key: str,
        preview: str,
        role: Role,
        expires_at: Optional[float] = None,
    ) -> None:
        self.id: str = id
        self.user_id: str = user_id
        self.name: str = name
        self.raw_key: str = raw_key
        self.preview: str = preview
        self.role: Role = role
        self.created_at: float = time.time()
        self.expires_at: Optional[float] = expires_at

    def to_response(self, include_raw: bool = False) -> ApiKeyResponse:
        return ApiKeyResponse(
            id=self.id,
            name=self.name,
            key_preview=self.preview,
            raw_key=self.raw_key if include_raw else None,
            role=self.role,
            created_at=self.created_at,
            expires_at=self.expires_at,
        )


def _safe_schedule(coro) -> None:
    """Schedule coroutine in current event loop if one is active, else close it."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        coro.close()


class UserRepository:
    """Manages users, authentication records, and scoped API keys in PostgreSQL / SQLite."""

    def __init__(self) -> None:
        self._users_by_id: Dict[str, StoredUser] = {}
        self._users_by_email: Dict[str, StoredUser] = {}
        self._api_keys_by_key: Dict[str, StoredApiKey] = {}
        self._api_keys_by_id: Dict[str, StoredApiKey] = {}

    def is_empty(self) -> bool:
        return len(self._users_by_id) == 0

    async def load_from_db(self) -> None:
        """Hydrate in-memory repository cache from PostgreSQL / SQLite."""
        try:
            factory = get_session_factory()
            async with factory() as session:
                user_stmt = select(UserModel)
                user_res = await session.execute(user_stmt)
                db_users = user_res.scalars().all()
                for u in db_users:
                    role = Role.ADMIN if u.role == "admin" else Role.DEVELOPER
                    stored_u = StoredUser(
                        id=u.id,
                        email=u.email,
                        name=u.name,
                        password_hash=u.password_hash,
                        role=role,
                    )
                    stored_u.created_at = u.created_at
                    self._users_by_id[stored_u.id] = stored_u
                    self._users_by_email[stored_u.email.lower()] = stored_u

                key_stmt = select(ApiKeyModel)
                key_res = await session.execute(key_stmt)
                db_keys = key_res.scalars().all()
                for k in db_keys:
                    role = Role.ADMIN if k.role == "admin" else Role.DEVELOPER
                    stored_k = StoredApiKey(
                        id=k.id,
                        user_id=k.user_id,
                        name=k.name,
                        raw_key=k.raw_key,
                        preview=k.preview,
                        role=role,
                        expires_at=k.expires_at,
                    )
                    stored_k.created_at = k.created_at
                    self._api_keys_by_key[stored_k.raw_key] = stored_k
                    self._api_keys_by_id[stored_k.id] = stored_k

                logger.info("Loaded %d users and %d API keys from DB into cache", len(db_users), len(db_keys))
        except Exception as e:
            logger.debug("Database load bypassed or table not ready: %s", e)

    async def _persist_user(self, stored: StoredUser) -> None:
        try:
            factory = get_session_factory()
            async with factory() as session:
                db_user = UserModel(
                    id=stored.id,
                    email=stored.email,
                    name=stored.name,
                    password_hash=stored.password_hash,
                    role=stored.role.value,
                    created_at=stored.created_at,
                    updated_at=stored.created_at,
                )
                session.add(db_user)
                await session.commit()
        except Exception as e:
            logger.warning("Failed to persist user '%s' to database: %s", stored.email, e)

    async def _persist_role_update(self, user_id: str, new_role: Role) -> None:
        try:
            factory = get_session_factory()
            async with factory() as session:
                db_user = await session.get(UserModel, user_id)
                if db_user:
                    db_user.role = new_role.value
                    db_user.updated_at = time.time()
                    await session.commit()
        except Exception as e:
            logger.warning("Failed to persist role update for user '%s': %s", user_id, e)

    async def _persist_api_key(self, stored: StoredApiKey) -> None:
        try:
            factory = get_session_factory()
            async with factory() as session:
                db_key = ApiKeyModel(
                    id=stored.id,
                    user_id=stored.user_id,
                    name=stored.name,
                    raw_key=stored.raw_key,
                    preview=stored.preview,
                    role=stored.role.value,
                    created_at=stored.created_at,
                    expires_at=stored.expires_at,
                )
                session.add(db_key)
                await session.commit()
        except Exception as e:
            logger.warning("Failed to persist API key '%s': %s", stored.id, e)

    async def _persist_revoke_key(self, key_id: str) -> None:
        try:
            factory = get_session_factory()
            async with factory() as session:
                db_key = await session.get(ApiKeyModel, key_id)
                if db_key:
                    await session.delete(db_key)
                    await session.commit()
        except Exception as e:
            logger.warning("Failed to revoke API key '%s' in database: %s", key_id, e)

    def create_user(self, data: UserCreate, force_role: Optional[Role] = None) -> UserResponse:
        """Create user in memory and schedule database persistence (defaults to DEVELOPER)."""
        email_lower = data.email.lower()
        if email_lower in self._users_by_email:
            raise ValueError("A user with this email already exists")

        assigned_role = force_role or data.role or Role.DEVELOPER
        user_id = str(uuid.uuid4())
        pwd_hash = hash_password(data.password)
        stored = StoredUser(
            id=user_id,
            email=email_lower,
            name=data.name,
            password_hash=pwd_hash,
            role=assigned_role,
        )
        self._users_by_id[user_id] = stored
        self._users_by_email[email_lower] = stored

        _safe_schedule(self._persist_user(stored))
        return stored.to_response()

    async def create_user_async(self, data: UserCreate, force_role: Optional[Role] = None) -> UserResponse:
        """Create user and await database write."""
        resp = self.create_user(data, force_role=force_role)
        stored = self._users_by_id[resp.id]
        await self._persist_user(stored)
        return resp

    def get_by_email(self, email: str) -> Optional[StoredUser]:
        return self._users_by_email.get(email.lower())

    def get_by_id(self, user_id: str) -> Optional[StoredUser]:
        return self._users_by_id.get(user_id)

    def list_users(self) -> List[UserResponse]:
        return [u.to_response() for u in self._users_by_id.values()]

    def update_role(self, user_id: str, new_role: Role) -> Optional[UserResponse]:
        """Update role in memory and schedule database write."""
        user = self._users_by_id.get(user_id)
        if not user:
            return None
        user.role = new_role
        _safe_schedule(self._persist_role_update(user_id, new_role))
        return user.to_response()

    async def update_role_async(self, user_id: str, new_role: Role) -> Optional[UserResponse]:
        """Update role and await database commit."""
        resp = self.update_role(user_id, new_role)
        if resp:
            await self._persist_role_update(user_id, new_role)
        return resp

    # API Keys
    def create_api_key(
        self,
        user_id: str,
        name: str,
        role: Role,
        expires_in_days: Optional[int] = 30,
    ) -> ApiKeyResponse:
        raw_key, preview = generate_api_key()
        key_id = str(uuid.uuid4())[:8]
        expires_at = (time.time() + (expires_in_days * 86400)) if expires_in_days else None

        stored = StoredApiKey(
            id=key_id,
            user_id=user_id,
            name=name,
            raw_key=raw_key,
            preview=preview,
            role=role,
            expires_at=expires_at,
        )
        self._api_keys_by_key[raw_key] = stored
        self._api_keys_by_id[key_id] = stored
        _safe_schedule(self._persist_api_key(stored))
        return stored.to_response(include_raw=True)

    async def create_api_key_async(
        self,
        user_id: str,
        name: str,
        role: Role,
        expires_in_days: Optional[int] = 30,
    ) -> ApiKeyResponse:
        resp = self.create_api_key(user_id, name, role, expires_in_days)
        stored = self._api_keys_by_id[resp.id]
        await self._persist_api_key(stored)
        return resp

    def get_api_key(self, raw_key: str) -> Optional[StoredApiKey]:
        key = self._api_keys_by_key.get(raw_key)
        if key and key.expires_at and time.time() > key.expires_at:
            return None
        return key

    def list_api_keys(self, user_id: str) -> List[ApiKeyResponse]:
        return [
            k.to_response(include_raw=False)
            for k in self._api_keys_by_id.values()
            if k.user_id == user_id
        ]

    def revoke_api_key(self, key_id: str, user_id: str) -> bool:
        stored = self._api_keys_by_id.get(key_id)
        if stored and stored.user_id == user_id:
            del self._api_keys_by_id[key_id]
            self._api_keys_by_key.pop(stored.raw_key, None)
            _safe_schedule(self._persist_revoke_key(key_id))
            return True
        return False

    async def revoke_api_key_async(self, key_id: str, user_id: str) -> bool:
        success = self.revoke_api_key(key_id, user_id)
        if success:
            await self._persist_revoke_key(key_id)
        return success

    def clear(self) -> None:
        """Reset repository state (useful for testing)."""
        self._users_by_id.clear()
        self._users_by_email.clear()
        self._api_keys_by_key.clear()
        self._api_keys_by_id.clear()


# Global User repository singleton
user_repo = UserRepository()

