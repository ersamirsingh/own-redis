"""Unit tests for Argon2id hashing, JWT tokens, user repository, and audit logging."""

import pytest
from pyredis.auth import (
    AuditLogger,
    UserCreate,
    UserRepository,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    hash_password,
    verify_password,
)
from pyredis.core.exceptions import AuthError
from pyredis.core.types import Role


class TestSecurity:
    def test_argon2_password_hashing(self) -> None:
        pwd = "SecretPassword123!"
        hashed = hash_password(pwd)

        assert hashed.startswith("$argon2id$")
        assert verify_password(pwd, hashed) is True
        assert verify_password("WrongPassword", hashed) is False

    def test_jwt_tokens(self) -> None:
        user_id = "user-123"
        email = "alice@example.com"
        access = create_access_token(user_id, email, Role.ADMIN)
        refresh = create_refresh_token(user_id, email, Role.ADMIN)

        # Decode access token
        payload_access = decode_token(access, expected_type="access")
        assert payload_access["sub"] == user_id
        assert payload_access["email"] == email
        assert payload_access["role"] == "admin"

        # Decode refresh token
        payload_refresh = decode_token(refresh, expected_type="refresh")
        assert payload_refresh["sub"] == user_id
        assert payload_refresh["type"] == "refresh"

        # Type mismatch must raise AuthError
        with pytest.raises(AuthError):
            decode_token(access, expected_type="refresh")

    def test_api_key_generation(self) -> None:
        raw, preview = generate_api_key()
        assert raw.startswith("sk-pyredis-")
        assert preview.startswith("sk-pyredis-...")
        assert raw.endswith(preview[-4:])


class TestUserRepository:
    def test_first_user_is_admin(self) -> None:
        repo = UserRepository()
        u1 = repo.create_user(UserCreate(email="first@example.com", name="Admin", password="pwd123password"))
        assert u1.role == Role.ADMIN

        # Second user defaults to DEVELOPER
        u2 = repo.create_user(UserCreate(email="second@example.com", name="Dev", password="pwd123password"))
        assert u2.role == Role.DEVELOPER

    def test_duplicate_email_rejected(self) -> None:
        repo = UserRepository()
        repo.create_user(UserCreate(email="dupe@example.com", name="User1", password="pwd123password"))
        with pytest.raises(ValueError):
            repo.create_user(UserCreate(email="dupe@example.com", name="User2", password="pwd123password"))

    def test_api_keys_management(self) -> None:
        repo = UserRepository()
        user = repo.create_user(UserCreate(email="api@example.com", name="ApiUser", password="pwd123password"))

        api_key = repo.create_api_key(user.id, "Prod Service", Role.DEVELOPER)
        assert api_key.raw_key is not None

        # Lookup by raw key
        stored = repo.get_api_key(api_key.raw_key)
        assert stored is not None
        assert stored.name == "Prod Service"
        assert stored.role == Role.DEVELOPER

        # Revoke
        assert repo.revoke_api_key(api_key.id, user.id) is True
        assert repo.get_api_key(api_key.raw_key) is None


class TestAuditLogger:
    def test_audit_logging(self) -> None:
        audit = AuditLogger(max_entries=10)
        audit.log(
            actor_id="u-1",
            actor_email="admin@example.com",
            actor_role=Role.ADMIN,
            action="SNAPSHOT_TRIGGERED",
            target="dump.rdb",
        )
        entries = audit.list_entries()
        assert len(entries) == 1
        assert entries[0]["action"] == "SNAPSHOT_TRIGGERED"
        assert entries[0]["actor_email"] == "admin@example.com"
