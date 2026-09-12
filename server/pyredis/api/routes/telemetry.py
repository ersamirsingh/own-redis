"""Telemetry, observability, persistence, eviction, and administrative management routes."""

from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from pyredis.api.deps import get_current_user, require_role
from pyredis.api.routes.keys import get_store
from pyredis.auth.audit import audit_logger
from pyredis.auth.models import UserResponse
from pyredis.auth.repository import user_repo
from pyredis.core.types import EvictionPolicy, Role
from pyredis.eviction.policy import EvictionManager
from pyredis.expiration.manager import ExpirationManager
from pyredis.metrics import metrics_collector
from pyredis.persistence.aof import AofEngine
from pyredis.persistence.snapshot import SnapshotEngine
from pyredis.tracing import tracer

router = APIRouter(tags=["Telemetry & Admin"])

# Subsystem references
_exp_ref: Optional[ExpirationManager] = None
_evict_ref: Optional[EvictionManager] = None
_aof_ref: Optional[AofEngine] = None
_snap_ref: Optional[SnapshotEngine] = None


def set_telemetry_references(
    exp: ExpirationManager,
    evict: EvictionManager,
    aof: AofEngine,
    snap: SnapshotEngine,
) -> None:
    global _exp_ref, _evict_ref, _aof_ref, _snap_ref
    _exp_ref = exp
    _evict_ref = evict
    _aof_ref = aof
    _snap_ref = snap


class EvictionPolicyUpdate(BaseModel):
    policy: EvictionPolicy
    weight_frequency: Optional[float] = None
    weight_recency_age: Optional[float] = None
    weight_ttl_urgency: Optional[float] = None
    weight_size: Optional[float] = None


class UserRoleUpdate(BaseModel):
    role: Role


@router.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok", "service": "pyredis"}


@router.get("/stats")
async def get_stats(
    current_user: Annotated[UserResponse, Depends(get_current_user)]
) -> Dict[str, Any]:
    """Overview dashboard statistics: memory, keys, ops/sec, hit ratio, latency."""
    store = get_store()
    summary = metrics_collector.get_summary()
    summary["memory_used_bytes"] = store.memory_usage()
    summary["total_keys"] = store.dbsize()
    if _evict_ref:
        summary["temperature"] = _evict_ref.get_temperature_stats()
    return summary


@router.get("/metrics")
async def get_metrics(
    current_user: Annotated[UserResponse, Depends(get_current_user)]
) -> Dict[str, Any]:
    """Detailed command analytics, latency percentiles, and hot-key traffic."""
    return metrics_collector.get_summary()


@router.get("/traces")
async def list_traces(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
    command: Optional[str] = None,
    status: Optional[str] = None,
    min_duration_ms: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """List recent distributed traces for Trace Explorer."""
    return tracer.list_traces(limit=limit, command=command, status=status, min_duration_ms=min_duration_ms)


@router.get("/traces/{trace_id}")
async def get_trace(
    trace_id: str,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Retrieve full waterfall trace with per-stage timing breakdown."""
    trace = tracer.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


@router.get("/ttl")
async def get_ttl_stats(
    current_user: Annotated[UserResponse, Depends(get_current_user)]
) -> Dict[str, Any]:
    """TTL distribution, expiring soon, and active expiration statistics."""
    if _exp_ref:
        return _exp_ref.get_metrics()
    return {}


@router.get("/persistence")
async def get_persistence_status(
    current_user: Annotated[UserResponse, Depends(get_current_user)]
) -> Dict[str, Any]:
    """AOF and snapshot engine operational telemetry."""
    return {
        "aof": _aof_ref.get_status() if _aof_ref else {},
        "snapshot": _snap_ref.get_status() if _snap_ref else {},
    }


@router.post("/persistence/snapshot")
async def trigger_snapshot(
    current_user: Annotated[UserResponse, Depends(require_role(Role.ADMIN))]
) -> Dict[str, Any]:
    """Trigger manual background snapshot (requires Admin role)."""
    if not _snap_ref:
        raise HTTPException(status_code=500, detail="Snapshot engine not configured")
    store = get_store()
    keys_saved = await _snap_ref.bgsave(store)

    audit_logger.log(
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=current_user.role,
        action="PERSISTENCE_SNAPSHOT_TRIGGERED",
        outcome="SUCCESS",
        details={"keys_saved": keys_saved},
    )
    return {"status": "OK", "keys_saved": keys_saved}


@router.get("/eviction")
async def get_eviction_status(
    current_user: Annotated[UserResponse, Depends(get_current_user)]
) -> Dict[str, Any]:
    """Eviction policy status, weights, and temperature distribution."""
    if not _evict_ref:
        return {}
    return {
        "policy": _evict_ref.policy.value,
        "max_memory": _evict_ref.max_memory,
        "evictions_total": _evict_ref.evictions_total,
        "weights": {
            "frequency": _evict_ref.weight_frequency,
            "recency": _evict_ref.weight_recency_age,
            "ttl": _evict_ref.weight_ttl_urgency,
            "size": _evict_ref.weight_size,
        },
        "temperature": _evict_ref.get_temperature_stats(),
    }


@router.patch("/eviction/policy")
async def update_eviction_policy(
    data: EvictionPolicyUpdate,
    current_user: Annotated[UserResponse, Depends(require_role(Role.ADMIN))],
) -> Dict[str, Any]:
    """Change memory eviction policy or tune adaptive weights (requires Admin role)."""
    if not _evict_ref:
        raise HTTPException(status_code=500, detail="Eviction manager not configured")

    _evict_ref.set_policy(data.policy)
    if data.weight_frequency is not None:
        _evict_ref.set_adaptive_weights(
            weight_frequency=data.weight_frequency,
            weight_recency_age=data.weight_recency_age or _evict_ref.weight_recency_age,
            weight_ttl_urgency=data.weight_ttl_urgency or _evict_ref.weight_ttl_urgency,
            weight_size=data.weight_size or _evict_ref.weight_size,
        )

    audit_logger.log(
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=current_user.role,
        action="EVICTION_POLICY_UPDATED",
        outcome="SUCCESS",
        details={"new_policy": data.policy.value},
    )
    return {"status": "OK", "policy": _evict_ref.policy.value}


@router.get("/audit-log")
async def list_audit_log(
    current_user: Annotated[UserResponse, Depends(require_role(Role.ADMIN))],
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = None,
    actor: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Query administrative and security audit trail (requires Admin role)."""
    return await audit_logger.list_entries_async(limit=limit, action=action, actor=actor)


@router.get("/users")
async def list_users(
    current_user: Annotated[UserResponse, Depends(require_role(Role.ADMIN))],
) -> List[UserResponse]:
    """List all registered platform users (requires Admin role)."""
    return user_repo.list_users()


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    data: UserRoleUpdate,
    current_user: Annotated[UserResponse, Depends(require_role(Role.ADMIN))],
) -> UserResponse:
    """Promote or demote a user's role (requires Admin role). Any Admin can make another user Admin or Developer."""
    updated = await user_repo.update_role_async(user_id, data.role)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    audit_logger.log(
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=current_user.role,
        action="USER_ROLE_UPDATED",
        target=user_id,
        outcome="SUCCESS",
        details={"new_role": data.role.value, "updated_by": current_user.email},
    )
    return updated

