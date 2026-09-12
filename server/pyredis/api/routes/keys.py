"""Operational Data Console Key Explorer and Editor routes."""

import fnmatch
import json
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from pyredis.api.deps import get_current_user, require_role
from pyredis.auth.audit import audit_logger
from pyredis.auth.models import UserResponse
from pyredis.core.types import DataType, Role
from pyredis.eviction.policy import EvictionManager
from pyredis.features.history import history_manager
from pyredis.storage import (
    DataStore,
    create_hash,
    create_json,
    create_list,
    create_set,
    create_string,
    create_zset,
)

router = APIRouter(prefix="/keys", tags=["Data Console"])

# Shared storage instance provided by app state or default singleton
_store_ref: Optional[DataStore] = None
_evict_ref: Optional[EvictionManager] = None


def set_storage_reference(store: DataStore, evict: EvictionManager) -> None:
    global _store_ref, _evict_ref
    _store_ref = store
    _evict_ref = evict


def get_store() -> DataStore:
    if _store_ref is None:
        raise HTTPException(status_code=500, detail="Data store not initialized")
    return _store_ref


class KeySummary(BaseModel):
    key: str
    type: str
    memory_bytes: int
    ttl_seconds: Optional[float]
    temperature: str
    access_count: int


class KeyListResponse(BaseModel):
    total: int
    keys: List[KeySummary]


class KeyDetailResponse(BaseModel):
    key: str
    type: str
    value: Any
    memory_bytes: int
    ttl_seconds: Optional[float]
    temperature: str
    access_count: int
    created_at: float
    last_accessed_at: float


class KeyCreateRequest(BaseModel):
    key: str
    type: DataType = DataType.STRING
    value: Any
    ttl_seconds: Optional[int] = None


@router.get("", response_model=KeyListResponse)
async def list_keys(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    pattern: str = Query("*", description="Glob filter pattern"),
    data_type: Optional[DataType] = Query(None, description="Filter by data type"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> KeyListResponse:
    """List keys with pattern search, type filter, and pagination for Key Explorer."""
    store = get_store()
    all_keys = store.keys(pattern)

    filtered: List[KeySummary] = []
    for k in all_keys:
        obj = store.get(k)
        if obj is None:
            continue
        if data_type and obj.data_type != data_type:
            continue

        ttl = store.get_ttl(k)
        temp = _evict_ref.classify_temperature(k) if _evict_ref else "UNKNOWN"
        filtered.append(KeySummary(
            key=k,
            type=obj.data_type.value,
            memory_bytes=obj.estimated_bytes,
            ttl_seconds=ttl if (ttl is not None and ttl >= 0) else None,
            temperature=temp,
            access_count=obj.access_count,
        ))

    total = len(filtered)
    paged = filtered[offset : offset + limit]
    return KeyListResponse(total=total, keys=paged)


@router.get("/{key}", response_model=KeyDetailResponse)
async def get_key(
    key: str,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> KeyDetailResponse:
    """Get full key details, raw value representation, and operational metadata."""
    store = get_store()
    obj = store.get(key)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Key '{key}' not found")

    ttl = store.get_ttl(key)
    temp = _evict_ref.classify_temperature(key) if _evict_ref else "UNKNOWN"

    # Format value for UI
    val: Any
    if obj.data_type == DataType.STRING:
        raw = obj.value
        val = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    elif obj.data_type == DataType.LIST:
        val = [
            x.decode("utf-8", errors="replace") if isinstance(x, bytes) else str(x)
            for x in obj.value
        ]
    elif obj.data_type == DataType.SET:
        val = [
            x.decode("utf-8", errors="replace") if isinstance(x, bytes) else str(x)
            for x in sorted(list(obj.value), key=lambda x: str(x))
        ]
    elif obj.data_type == DataType.HASH:
        val = {
            (k.decode("utf-8", errors="replace") if isinstance(k, bytes) else str(k)): (
                v.decode("utf-8", errors="replace") if isinstance(v, bytes) else str(v)
            )
            for k, v in obj.value.items()
        }
    elif obj.data_type == DataType.ZSET:
        score_map, _ = obj.value
        val = [{"member": m, "score": s} for m, s in score_map.items()]
    elif obj.data_type == DataType.JSON:
        val = obj.value
    else:
        val = str(obj.value)

    return KeyDetailResponse(
        key=key,
        type=obj.data_type.value,
        value=val,
        memory_bytes=obj.estimated_bytes,
        ttl_seconds=ttl if (ttl is not None and ttl >= 0) else None,
        temperature=temp,
        access_count=obj.access_count,
        created_at=obj.created_at,
        last_accessed_at=obj.last_accessed_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_or_update_key(
    data: KeyCreateRequest,
    current_user: Annotated[UserResponse, Depends(require_role(Role.DEVELOPER))],
) -> Dict[str, Any]:
    """Create or update a key with type-specific validation (requires Developer+ role)."""
    store = get_store()
    now_exp = None
    if data.ttl_seconds and data.ttl_seconds > 0:
        import time
        now_exp = time.time() + data.ttl_seconds

    # Construct typed object
    if data.type == DataType.STRING:
        raw_bytes = str(data.value).encode("utf-8")
        store.set(data.key, create_string(raw_bytes), expire_at=now_exp)

    elif data.type == DataType.LIST:
        if not isinstance(data.value, list):
            raise HTTPException(status_code=400, detail="List value must be an array")
        raw_items = [str(x).encode("utf-8") for x in data.value]
        store.set(data.key, create_list(raw_items), expire_at=now_exp)

    elif data.type == DataType.SET:
        if not isinstance(data.value, list):
            raise HTTPException(status_code=400, detail="Set value must be an array")
        raw_set = {str(x).encode("utf-8") for x in data.value}
        store.set(data.key, create_set(raw_set), expire_at=now_exp)

    elif data.type == DataType.HASH:
        if not isinstance(data.value, dict):
            raise HTTPException(status_code=400, detail="Hash value must be a JSON object")
        raw_hash = {
            str(k).encode("utf-8"): str(v).encode("utf-8")
            for k, v in data.value.items()
        }
        store.set(data.key, create_hash(raw_hash), expire_at=now_exp)

    elif data.type == DataType.ZSET:
        if not isinstance(data.value, list):
            raise HTTPException(status_code=400, detail="Sorted Set value must be an array of {member, score}")
        z_obj = create_zset()
        score_map, sl = z_obj.value
        for item in data.value:
            m = str(item.get("member", ""))
            s = float(item.get("score", 0.0))
            score_map[m] = s
            sl.insert(s, m)
        z_obj.update_size()
        store.set(data.key, z_obj, expire_at=now_exp)

    elif data.type == DataType.JSON:
        if isinstance(data.value, str):
            try:
                parsed_json = json.loads(data.value)
            except Exception:
                parsed_json = data.value
        else:
            parsed_json = data.value
        store.set(data.key, create_json(parsed_json), expire_at=now_exp)

    audit_logger.log(
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=current_user.role,
        action="KEY_CREATE_OR_UPDATE",
        target=data.key,
        outcome="SUCCESS",
        details={"type": data.type.value, "ttl": data.ttl_seconds},
    )

    return {"status": "OK", "key": data.key, "type": data.type.value}


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    key: str,
    current_user: Annotated[UserResponse, Depends(require_role(Role.DEVELOPER))],
) -> None:
    """Delete a key from the database (requires Developer+ role)."""
    store = get_store()
    deleted = store.delete(key)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Key '{key}' not found")

    audit_logger.log(
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=current_user.role,
        action="KEY_DELETE",
        target=key,
        outcome="SUCCESS",
    )


@router.get("/{key}/history")
async def get_key_history(
    key: str,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> List[Dict[str, Any]]:
    """Retrieve version history and previous snapshots of a key."""
    return history_manager.get_history(key)
