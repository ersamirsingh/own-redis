"""In-memory User and API Key Repository with multi-role support."""

import time
import uuid
from typing import Dict, List, Optional, Tuple
from pyredis.auth.models import ApiKeyResponse, UserCreate, UserResponse
from pyredis.auth.security import generate_api_key, hash_password
from pyredis.core.types import Role


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


class UserRepository:
    """Manages users, authentication records, and scoped API keys."""

    def __init__(self) -> None:
        self._users_by_id: Dict[str, StoredUser] = {}
        self._users_by_email: Dict[str, StoredUser] = {}
        self._api_keys_by_key: Dict[str, StoredApiKey] = {}
        self._api_keys_by_id: Dict[str, StoredApiKey] = {}

    def is_empty(self) -> bool:
        return len(self._users_by_id) == 0

    def create_user(self, data: UserCreate, force_role: Optional[Role] = None) -> UserResponse:
        """Create a new user. If it's the first user, default to ADMIN."""
        email_lower = data.email.lower()
        if email_lower in self._users_by_email:
            raise ValueError("A user with this email already exists")

        # First user is Admin if role unspecified
        if force_role:
            assigned_role = force_role
        elif data.role:
            assigned_role = data.role
        elif self.is_empty():
            assigned_role = Role.ADMIN
        else:
            assigned_role = Role.DEVELOPER

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
        return stored.to_response()

    def get_by_email(self, email: str) -> Optional[StoredUser]:
        return self._users_by_email.get(email.lower())

    def get_by_id(self, user_id: str) -> Optional[StoredUser]:
        return self._users_by_id.get(user_id)

    def list_users(self) -> List[UserResponse]:
        return [u.to_response() for u in self._users_by_id.values()]

    def update_role(self, user_id: str, new_role: Role) -> Optional[UserResponse]:
        user = self._users_by_id.get(user_id)
        if not user:
            return None
        user.role = new_role
        return user.to_response()

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
        return stored.to_response(include_raw=True)

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
            return True
        return False

    def clear(self) -> None:
        """Reset repository state (useful for testing)."""
        self._users_by_id.clear()
        self._users_by_email.clear()
        self._api_keys_by_key.clear()
        self._api_keys_by_id.clear()


# Global User repository singleton
user_repo = UserRepository()
