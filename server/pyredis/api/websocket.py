"""Real-time authenticated WebSocket Gateway and Telemetry Broadcaster."""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect, status
from pyredis.auth.repository import user_repo
from pyredis.auth.security import decode_token
from pyredis.core.exceptions import AuthError
from pyredis.core.types import Role
from pyredis.events.bus import event_bus
from pyredis.events.types import Event, EventType

logger = logging.getLogger("pyredis.websocket")

SUPPORTED_TOPICS = {"telemetry", "keys", "events", "traces", "alerts"}


@dataclass
class WebSocketSession:
    """Represents an active, authenticated WebSocket client session."""
    client_id: str
    websocket: WebSocket
    user_id: str
    email: str
    role: Role
    topics: Set[str] = field(default_factory=lambda: {"telemetry", "events", "alerts"})
    connected_at: float = field(default_factory=time.time)


class WebSocketManager:
    """Manages connected clients, topic subscriptions, and real-time event broadcasting."""

    def __init__(self) -> None:
        self.sessions: Dict[str, WebSocketSession] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._get_stats_fn: Optional[Callable[[], Dict[str, Any]]] = None
        self._event_handler_installed: bool = False

    def authenticate_token(self, token: Optional[str]) -> Optional[Dict[str, Any]]:
        """Validate token (JWT or API Key) and return user payload."""
        if not token:
            return None

        # Check API Key
        if token.startswith("sk-pyredis-"):
            api_key = user_repo.get_api_key(token)
            if not api_key:
                return None
            stored_user = user_repo.get_by_id(api_key.user_id)
            if not stored_user:
                return None
            return {
                "sub": stored_user.id,
                "email": stored_user.email,
                "role": api_key.role,
            }

        # Check JWT Token
        try:
            payload = decode_token(token, expected_type="access")
            return {
                "sub": payload["sub"],
                "email": payload["email"],
                "role": Role(payload["role"]),
            }
        except (AuthError, Exception) as e:
            logger.debug(f"WebSocket auth failed: {e}")
            return None

    async def connect(
        self,
        websocket: WebSocket,
        token: Optional[str] = None,
    ) -> Optional[WebSocketSession]:
        """Authenticate and accept a new WebSocket connection."""
        self._loop = asyncio.get_running_loop()
        user_info = self.authenticate_token(token)
        if not user_info:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
            return None

        await websocket.accept()
        client_id = f"ws-{uuid.uuid4().hex[:8]}"
        session = WebSocketSession(
            client_id=client_id,
            websocket=websocket,
            user_id=user_info["sub"],
            email=user_info["email"],
            role=user_info["role"],
        )
        self.sessions[client_id] = session
        logger.info(f"WebSocket client connected: {client_id} (user: {session.email}, role: {session.role.value})")

        # Send welcome handshake
        await self.send_to(client_id, {
            "type": "welcome",
            "client_id": client_id,
            "email": session.email,
            "role": session.role.value,
            "subscribed_topics": list(session.topics),
            "timestamp": time.time(),
        })

        return session

    def disconnect(self, client_id: str) -> None:
        """Clean up on client disconnection."""
        if client_id in self.sessions:
            session = self.sessions.pop(client_id)
            logger.info(f"WebSocket client disconnected: {client_id} (user: {session.email})")

    def subscribe(self, client_id: str, topics: List[str]) -> List[str]:
        """Subscribe client to one or more valid topics."""
        session = self.sessions.get(client_id)
        if not session:
            return []
        for t in topics:
            if t in SUPPORTED_TOPICS:
                session.topics.add(t)
        return list(session.topics)

    def unsubscribe(self, client_id: str, topics: List[str]) -> List[str]:
        """Unsubscribe client from specified topics."""
        session = self.sessions.get(client_id)
        if not session:
            return []
        for t in topics:
            session.topics.discard(t)
        return list(session.topics)

    async def send_to(self, client_id: str, message: Dict[str, Any]) -> bool:
        """Send message directly to a specific connected client."""
        session = self.sessions.get(client_id)
        if not session:
            return False
        try:
            await session.websocket.send_text(json.dumps(message))
            return True
        except Exception as e:
            logger.warning(f"Failed to send to client {client_id}: {e}")
            self.disconnect(client_id)
            return False

    async def broadcast(self, topic: str, data: Dict[str, Any]) -> int:
        """Broadcast payload to all clients subscribed to a given topic."""
        message = {
            "topic": topic,
            "timestamp": time.time(),
            **data,
        }
        encoded = json.dumps(message)
        delivered = 0
        dead_clients: List[str] = []

        for client_id, session in list(self.sessions.items()):
            if topic in session.topics:
                try:
                    await session.websocket.send_text(encoded)
                    delivered += 1
                except Exception:
                    dead_clients.append(client_id)

        for cid in dead_clients:
            self.disconnect(cid)

        return delivered

    def _on_system_event(self, event: Event) -> None:
        if not self.sessions:
            return

        if event.type in (
            EventType.KEY_CREATED,
            EventType.KEY_UPDATED,
            EventType.KEY_DELETED,
            EventType.KEY_EXPIRED,
        ):
            topic = "keys"
        elif event.type in (EventType.SLOW_COMMAND, EventType.MEMORY_WARNING):
            topic = "alerts"
        else:
            topic = "events"

        payload = {
            "type": "event",
            "event_type": event.type.value,
            "data": event.to_dict(),
        }

        if self._loop and self._loop.is_running():
            try:
                current_loop = asyncio.get_running_loop()
                if current_loop is self._loop:
                    self._loop.create_task(self.broadcast(topic, payload))
                else:
                    asyncio.run_coroutine_threadsafe(self.broadcast(topic, payload), self._loop)
            except RuntimeError:
                asyncio.run_coroutine_threadsafe(self.broadcast(topic, payload), self._loop)
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.broadcast(topic, payload))
            except RuntimeError:
                pass

    def setup_event_bridge(self) -> None:
        """Wire EventBus system events to WebSocket topic broadcasting."""
        event_bus.subscribe("*", self._on_system_event)
        logger.info("WebSocket EventBus bridge initialized")

    def reset(self) -> None:
        """Reset sessions and loop references."""
        self.sessions.clear()
        self._loop = None

    def start_heartbeat(
        self,
        get_stats_fn: Callable[[], Dict[str, Any]],
        interval_seconds: float = 1.0,
    ) -> None:
        """Start periodic background task streaming live telemetry metrics."""
        self._get_stats_fn = get_stats_fn

        async def _heartbeat_loop() -> None:
            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    if not self.sessions:
                        continue
                    if self._get_stats_fn:
                        stats = self._get_stats_fn()
                        await self.broadcast("telemetry", {
                            "type": "telemetry",
                            "data": stats,
                        })
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in telemetry heartbeat loop: {e}")

        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(_heartbeat_loop())
            logger.info("WebSocket telemetry heartbeat started")

    async def stop_heartbeat(self) -> None:
        """Cancel background telemetry loop on server shutdown."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
            logger.info("WebSocket telemetry heartbeat stopped")


# Global WebSocket Manager singleton
ws_manager = WebSocketManager()
