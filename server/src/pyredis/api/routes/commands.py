"""In-browser Command Console execution route."""

import shlex
import time
from typing import Annotated, Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from pyredis.api.deps import get_current_user
from pyredis.api.routes.keys import get_store
from pyredis.auth.audit import audit_logger
from pyredis.auth.models import UserResponse
from pyredis.commands.registry import CommandContext, registry
from pyredis.core.exceptions import AuthError, CommandError, WrongTypeError
from pyredis.events import Event, EventType, event_bus
from pyredis.metrics import metrics_collector
from pyredis.protocol.types import Array, BulkString, Integer, SimpleError, SimpleString
from pyredis.tracing import tracer

router = APIRouter(prefix="/commands", tags=["Command Console"])


class CommandExecuteRequest(BaseModel):
    command: Optional[str] = None
    tokens: Optional[List[str]] = None


def _format_result(val: Any) -> Any:
    """Format internal and protocol types into JSON-friendly response."""
    if val is None:
        return None
    if isinstance(val, SimpleString):
        return val.value
    if isinstance(val, SimpleError):
        return f"-{val.code} {val.message}"
    if isinstance(val, Integer):
        return val.value
    if isinstance(val, BulkString):
        return val.value.decode("utf-8", errors="replace") if val.value is not None else None
    if isinstance(val, Array):
        return [_format_result(x) for x in (val.elements or [])]
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, (list, tuple)):
        return [_format_result(x) for x in val]
    if isinstance(val, dict):
        return {
            (k.decode("utf-8", errors="replace") if isinstance(k, bytes) else str(k)): (
                _format_result(v)
            )
            for k, v in val.items()
        }
    return val


@router.post("", status_code=status.HTTP_200_OK)
async def execute_command(
    data: CommandExecuteRequest,
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> Dict[str, Any]:
    """Execute a Redis command from the web console, gated by authenticated role."""
    tokens: List[str]
    if data.tokens:
        tokens = data.tokens
    elif data.command:
        try:
            tokens = shlex.split(data.command)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Command parse error: {e}")
    else:
        raise HTTPException(status_code=400, detail="Missing command or tokens")

    if not tokens:
        raise HTTPException(status_code=400, detail="Empty command")

    cmd_name = tokens[0].upper()
    cmd_args = tokens[1:]

    store = get_store()
    trace = tracer.start_trace(
        cmd_name,
        cmd_args,
        client_id=current_user.id,
        client_ip="web-console",
    )
    start_time = time.monotonic()

    context = CommandContext(
        store=store,
        role=current_user.role,
        client_id=current_user.id,
        authenticated=True,
        session_user=current_user.email,
        metrics=metrics_collector,
        tracer=tracer,
    )

    try:
        with tracer.span(trace, "storage"):
            raw_result = registry.execute(cmd_name, cmd_args, context)
        formatted_result = _format_result(raw_result)
        trace.finish(status="OK")
    except AuthError as e:
        trace.finish(status="ERROR", error_message=str(e))
        tracer.record_trace(trace)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (CommandError, WrongTypeError) as e:
        trace.finish(status="ERROR", error_message=str(e))
        tracer.record_trace(trace)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        trace.finish(status="ERROR", error_message=str(e))
        tracer.record_trace(trace)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    duration_ms = (time.monotonic() - start_time) * 1000.0
    tracer.record_trace(trace)

    first_key = cmd_args[0] if cmd_args else None
    metrics_collector.record_command(
        cmd_name,
        duration_ms,
        key=first_key,
        args=trace.sanitized_args,
        client_peer="web-console",
    )

    cmd_def = registry.get_definition(cmd_name)
    if cmd_def and cmd_def.is_mutation:
        audit_logger.log(
            actor_id=current_user.id,
            actor_email=current_user.email,
            actor_role=current_user.role,
            action=f"COMMAND_{cmd_name}",
            target=first_key,
            outcome="SUCCESS",
        )

    return {
        "command": cmd_name,
        "args": trace.sanitized_args,
        "result": formatted_result,
        "duration_ms": round(duration_ms, 3),
        "trace_id": trace.trace_id,
    }
