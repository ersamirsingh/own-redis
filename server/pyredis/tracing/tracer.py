"""Distributed Tracing with waterfall spans and PII argument masking."""

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Union

SENSITIVE_KEYWORDS = {"PASSWORD", "SECRET", "TOKEN", "AUTH", "KEY", "APIKEY", "CREDENTIAL"}


def sanitize_arguments(command: str, args: List[Union[bytes, str]]) -> List[str]:
    """Mask sensitive argument values to prevent PII/credentials leaking into trace logs."""
    sanitized: List[str] = []
    cmd_upper = command.upper()
    is_sensitive_cmd = cmd_upper in {"AUTH", "CONFIG"} or any(k in cmd_upper for k in SENSITIVE_KEYWORDS)

    for i, arg in enumerate(args):
        str_val = arg.decode("utf-8", errors="replace") if isinstance(arg, bytes) else str(arg)
        if is_sensitive_cmd and i > 0:
            sanitized.append("******")
        elif len(str_val) > 100:
            sanitized.append(str_val[:97] + "...")
        else:
            sanitized.append(str_val)
    return sanitized


@dataclass
class Span:
    """A discrete execution phase within a command lifecycle."""
    name: str
    start_time: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def finish(self) -> None:
        self.duration_ms = round((time.time() - self.start_time) * 1000.0, 3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "start_time": self.start_time,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


@dataclass
class Trace:
    """Complete lifecycle trace for an incoming request."""
    command: str
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_id: Optional[str] = None
    client_ip: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    status: str = "OK"
    error_message: Optional[str] = None
    sanitized_args: List[str] = field(default_factory=list)
    spans: List[Span] = field(default_factory=list)

    def add_span(self, span: Span) -> None:
        self.spans.append(span)

    def finish(self, status: str = "OK", error_message: Optional[str] = None) -> None:
        self.status = status
        self.error_message = error_message
        self.duration_ms = round((time.time() - self.start_time) * 1000.0, 3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "command": self.command,
            "client_id": self.client_id,
            "client_ip": self.client_ip,
            "start_time": self.start_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error_message": self.error_message,
            "sanitized_args": self.sanitized_args,
            "spans": [s.to_dict() for s in self.spans],
        }


class Tracer:
    """Ring buffer and collector for distributed traces across the engine."""

    def __init__(self, max_traces: int = 1000) -> None:
        self.max_traces: int = max_traces
        self._traces: List[Trace] = []

    def start_trace(
        self,
        command: str,
        args: Optional[List[Union[bytes, str]]] = None,
        client_id: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> Trace:
        """Initialize a new trace context."""
        sanitized = sanitize_arguments(command, args or [])
        trace = Trace(
            command=command.upper(),
            client_id=client_id,
            client_ip=client_ip,
            sanitized_args=sanitized,
        )
        return trace

    def record_trace(self, trace: Trace) -> None:
        """Store finished trace in circular buffer."""
        self._traces.append(trace)
        if len(self._traces) > self.max_traces:
            self._traces.pop(0)

    @contextmanager
    def span(self, trace: Trace, name: str, metadata: Optional[Dict[str, Any]] = None) -> Iterator[Span]:
        """Context manager to record timing and metadata for a stage span."""
        s = Span(name=name, metadata=metadata or {})
        try:
            yield s
        finally:
            s.finish()
            trace.add_span(s)

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve detailed waterfall trace by ID."""
        for t in reversed(self._traces):
            if t.trace_id == trace_id:
                return t.to_dict()
        return None

    def list_traces(
        self,
        limit: int = 50,
        command: Optional[str] = None,
        status: Optional[str] = None,
        min_duration_ms: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Filter and retrieve recent traces for Trace Explorer."""
        matches = []
        for t in reversed(self._traces):
            if command and t.command != command.upper():
                continue
            if status and t.status != status.upper():
                continue
            if min_duration_ms is not None and t.duration_ms < min_duration_ms:
                continue
            matches.append(t.to_dict())
            if len(matches) >= limit:
                break
        return matches

    def clear(self) -> None:
        self._traces.clear()


# Global Tracer singleton
tracer = Tracer()
