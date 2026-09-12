"""Authentication and API Key management routes."""

from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from pyredis.api.deps import get_current_user
from pyredis.auth.audit import audit_logger
from pyredis.auth.models import (
    ApiKeyCreate,
    ApiKeyResponse,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from pyredis.auth.repository import user_repo
from pyredis.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from pyredis.core.exceptions import AuthError
from pyredis.core.types import Role

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(data: UserCreate) -> TokenResponse:
    """Register a new user account (defaults to developer role)."""
    try:
        user = await user_repo.create_user_async(data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    access_token = create_access_token(user.id, user.email, user.role)
    refresh_token = create_refresh_token(user.id, user.email, user.role)

    audit_logger.log(
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action="AUTH_SIGNUP",
        outcome="SUCCESS",
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user,
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin) -> TokenResponse:
    """Authenticate with email and password to receive JWT tokens."""
    stored = user_repo.get_by_email(data.email)
    if not stored or not verify_password(data.password, stored.password_hash):
        audit_logger.log(
            actor_id="anonymous",
            actor_email=data.email,
            actor_role=Role.DEVELOPER,
            action="AUTH_LOGIN_FAILED",
            outcome="FAILURE",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    user = stored.to_response()
    access_token = create_access_token(user.id, user.email, user.role)
    refresh_token = create_refresh_token(user.id, user.email, user.role)

    audit_logger.log(
        actor_id=user.id,
        actor_email=user.email,
        actor_role=user.role,
        action="AUTH_LOGIN",
        outcome="SUCCESS",
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest) -> TokenResponse:
    """Rotate JWT access and refresh tokens using a valid refresh token."""
    try:
        payload = decode_token(data.refresh_token, expected_type="refresh")
        user_id = payload.get("sub")
        stored = user_repo.get_by_id(user_id)
        if not stored:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        user = stored.to_response()
        new_access = create_access_token(user.id, user.email, user.role)
        new_refresh = create_refresh_token(user.id, user.email, user.role)

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            user=user,
        )
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Annotated[UserResponse, Depends(get_current_user)]) -> UserResponse:
    """Return the profile and role of the currently authenticated user."""
    return current_user


@router.post("/api-keys", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: ApiKeyCreate,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> ApiKeyResponse:
    """Create a scoped personal API key for programmatic access."""
    # Only Admin can create an Admin-scoped API key
    if current_user.role != Role.ADMIN and data.role == Role.ADMIN:
        data.role = Role.DEVELOPER

    api_key = await user_repo.create_api_key_async(
        user_id=current_user.id,
        name=data.name,
        role=data.role,
        expires_in_days=data.expires_in_days,
    )

    audit_logger.log(
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=current_user.role,
        action="API_KEY_CREATED",
        target=api_key.id,
        outcome="SUCCESS",
        details={"name": data.name, "role": data.role.value},
    )

    return api_key


@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    current_user: Annotated[UserResponse, Depends(get_current_user)]
) -> List[ApiKeyResponse]:
    """List all API keys created by the current user."""
    return user_repo.list_api_keys(current_user.id)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: str,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> None:
    """Revoke a personal API key."""
    success = await user_repo.revoke_api_key_async(key_id, current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    audit_logger.log(
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=current_user.role,
        action="API_KEY_REVOKED",
        target=key_id,
        outcome="SUCCESS",
    )

