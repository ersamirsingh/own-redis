"""FastAPI dependency injection for authentication and role-based access control (RBAC)."""

from typing import Annotated, Callable, Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pyredis.auth.models import UserResponse
from pyredis.auth.repository import user_repo
from pyredis.auth.security import decode_token
from pyredis.commands.registry import ROLE_HIERARCHY
from pyredis.core.exceptions import AuthError
from pyredis.core.types import Role

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)]
) -> UserResponse:
    """Extract and verify user identity from Bearer token (JWT or API Key)."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # 1. API Key Authentication (sk-pyredis-...)
    if token.startswith("sk-pyredis-"):
        api_key = user_repo.get_api_key(token)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired API Key",
            )
        stored_user = user_repo.get_by_id(api_key.user_id)
        if not stored_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User associated with API Key not found",
            )
        # Use the role assigned to the specific API key
        return UserResponse(
            id=stored_user.id,
            email=stored_user.email,
            name=stored_user.name,
            role=api_key.role,
            created_at=stored_user.created_at,
        )

    # 2. JWT Access Token Authentication
    try:
        payload = decode_token(token, expected_type="access")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        stored_user = user_repo.get_by_id(user_id)
        if not stored_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account no longer exists",
            )
        return stored_user.to_response()

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(min_role: Role) -> Callable[[UserResponse], UserResponse]:
    """Dependency factory enforcing minimum required role privileges."""

    def role_checker(
        current_user: Annotated[UserResponse, Depends(get_current_user)]
    ) -> UserResponse:
        user_level = ROLE_HIERARCHY.get(current_user.role, 1)
        required_level = ROLE_HIERARCHY.get(min_role, 2)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: required role '{min_role.value}' or higher",
            )
        return current_user

    return role_checker
