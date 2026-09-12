"""Distributed lock inspection and administrative management routes."""

from typing import Annotated, Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from pyredis.api.deps import get_current_user, require_role
from pyredis.auth.audit import audit_logger
from pyredis.auth.models import UserResponse
from pyredis.core.types import Role
from pyredis.features.lock import lock_manager

router = APIRouter(prefix="/locks", tags=["Distributed Locks"])


class LockReleaseRequest(BaseModel):
    key: str


@router.get("")
async def list_locks(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> List[Dict[str, Any]]:
    """List all active distributed locks and lease statuses."""
    return lock_manager.list_locks()


@router.post("/force-release")
async def force_release_lock(
    data: LockReleaseRequest,
    current_user: Annotated[UserResponse, Depends(require_role(Role.OPERATOR))],
) -> Dict[str, Any]:
    """Administratively release an active lock (requires Operator+ role)."""
    released = lock_manager.force_release(data.key)
    if not released:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lock not found or already released")

    audit_logger.log(
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=current_user.role,
        action="LOCK_FORCE_RELEASED",
        target=data.key,
        outcome="SUCCESS",
    )
    return {"status": "OK", "key": data.key}
