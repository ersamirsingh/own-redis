"""AI intelligence routes: autonomous DBA diagnostics, chat assistant, and semantic memory."""

import json
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from pyredis.ai.diagnostics import diagnostics_engine
from pyredis.ai.memory import semantic_memory
from pyredis.ai.provider import gemini_provider
from pyredis.api.deps import get_current_user, require_role
from pyredis.api.routes.keys import get_store
from pyredis.api.routes.telemetry import _evict_ref, _exp_ref
from pyredis.auth.audit import audit_logger
from pyredis.auth.models import UserResponse
from pyredis.commands.registry import CommandContext, registry
from pyredis.core.types import Role

router = APIRouter(prefix="/ai", tags=["AI Intelligence"])


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = None


class ActionExecuteRequest(BaseModel):
    action_id: str


class MemoryAddRequest(BaseModel):
    text: str
    id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MemorySearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    min_score: Optional[float] = 0.0


class AiSettingsUpdate(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = None


@router.get("/diagnostics")
async def run_diagnostics(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Execute grounded telemetry diagnosis and return DBA health report."""
    store = get_store()
    return await diagnostics_engine.run_diagnostics(
        store=store,
        evict_mgr=_evict_ref,
        exp_mgr=_exp_ref,
    )


@router.post("/chat")
async def chat_assistant(
    data: ChatRequest,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Interact with autonomous DBA Assistant with grounded telemetry context."""
    store = get_store()
    telemetry = diagnostics_engine.collect_telemetry_context(
        store=store,
        evict_mgr=_evict_ref,
        exp_mgr=_exp_ref,
    )

    system_instruction = (
        "You are the PyRedis AI Database Administrator and Performance Architect.\n"
        "You help engineers optimize database queries, configure eviction policies, "
        "understand latency profiles, and structure in-memory data efficiently.\n"
        f"Live Engine Telemetry:\n{json.dumps(telemetry, indent=2)}\n\n"
        "Ground your advice strictly in the provided engine state. "
        "Recommend specific PyRedis commands where applicable."
    )

    prompt = data.message
    if data.history:
        history_str = "\n".join(f"{m.role.upper()}: {m.content}" for m in data.history[-5:])
        prompt = f"Previous conversation:\n{history_str}\n\nUSER: {data.message}"

    reply = await gemini_provider.generate_text_async(
        prompt=prompt,
        system_instruction=system_instruction,
    )

    return {
        "reply": reply,
        "context_used": telemetry,
    }


@router.post("/actions/execute")
async def execute_proposed_action(
    data: ActionExecuteRequest,
    current_user: Annotated[UserResponse, Depends(require_role(Role.ADMIN))],
) -> Dict[str, Any]:
    """Execute an approved AI-proposed diagnostic action (requires Admin role)."""
    action = diagnostics_engine.get_proposed_action(data.action_id)
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposed action not found or expired",
        )

    store = get_store()
    cmd_line = action.get("command", "")
    parts = cmd_line.split()
    if not parts:
        raise HTTPException(status_code=400, detail="Invalid action command")

    cmd_name = parts[0].upper()
    cmd_args = parts[1:]

    context = CommandContext(
        store=store,
        role=current_user.role,
        session_user=current_user.email,
    )

    try:
        result = registry.execute(cmd_name, cmd_args, context)
        audit_logger.log(
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_role=current_user.role,
            action="AI_ACTION_EXECUTED",
            target=data.action_id,
            outcome="SUCCESS",
            details={"command": cmd_line, "result": str(result)},
        )
        return {"status": "SUCCESS", "action_id": data.action_id, "result": str(result)}
    except Exception as e:
        audit_logger.log(
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_role=current_user.role,
            action="AI_ACTION_EXECUTED",
            target=data.action_id,
            outcome="FAILED",
            details={"command": cmd_line, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Action execution failed: {e}")


@router.get("/memory")
async def list_semantic_memory(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """List semantic memory entries."""
    return semantic_memory.list_entries(limit=limit)


@router.post("/memory")
async def add_semantic_memory(
    data: MemoryAddRequest,
    current_user: Annotated[UserResponse, Depends(require_role(Role.DEVELOPER))],
) -> Dict[str, Any]:
    """Store document in semantic memory with vector embedding (requires Developer+ role)."""
    entry_id = await semantic_memory.add_async(
        text=data.text,
        id=data.id,
        metadata=data.metadata,
    )
    return {"status": "OK", "id": entry_id}


@router.post("/memory/search")
async def search_semantic_memory(
    data: MemorySearchRequest,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> List[Dict[str, Any]]:
    """Search semantic memory vectors by natural language similarity."""
    return await semantic_memory.search_async(
        query=data.query,
        top_k=data.top_k or 5,
        min_score=data.min_score or 0.0,
    )


@router.delete("/memory/{entry_id}")
async def delete_semantic_memory(
    entry_id: str,
    current_user: Annotated[UserResponse, Depends(require_role(Role.DEVELOPER))],
) -> Dict[str, Any]:
    """Delete entry from semantic memory (requires Developer+ role)."""
    deleted = semantic_memory.delete(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    return {"status": "OK", "id": entry_id}


@router.get("/settings")
async def get_ai_settings(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Get active AI provider status and configured model."""
    masked_key = None
    if gemini_provider.api_key:
        masked_key = f"...{gemini_provider.api_key[-4:]}" if len(gemini_provider.api_key) > 4 else "***"

    return {
        "provider": "Google Gemini",
        "is_configured": gemini_provider.is_configured,
        "model": gemini_provider.model_name,
        "embedding_model": gemini_provider.embedding_model,
        "masked_api_key": masked_key,
    }


@router.post("/settings")
async def update_ai_settings(
    data: AiSettingsUpdate,
    current_user: Annotated[UserResponse, Depends(require_role(Role.ADMIN))],
) -> Dict[str, Any]:
    """Update AI API key and model at runtime (requires Admin role)."""
    gemini_provider.update_config(api_key=data.api_key, model=data.model)
    audit_logger.log(
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=current_user.role,
        action="AI_SETTINGS_UPDATED",
        outcome="SUCCESS",
        details={"model": gemini_provider.model_name, "has_key": bool(data.api_key)},
    )
    return {
        "status": "OK",
        "is_configured": gemini_provider.is_configured,
        "model": gemini_provider.model_name,
    }
