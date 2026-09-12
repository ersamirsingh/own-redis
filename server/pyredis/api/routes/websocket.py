"""WebSocket routing and client message dispatch."""

import json
import logging
import time
from typing import Optional
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pyredis.api.routes.keys import get_store
from pyredis.api.websocket import ws_manager
from pyredis.metrics import metrics_collector

logger = logging.getLogger("pyredis.routes.websocket")

router = APIRouter(tags=["Real-time Gateway"])


def get_current_telemetry_snapshot():
    """Helper to collect current live telemetry dictionary."""
    store = get_store()
    summary = metrics_collector.get_summary()
    summary["memory_used_bytes"] = store.memory_usage()
    summary["total_keys"] = store.dbsize()
    return summary


@router.websocket("/ws")
@router.websocket("/api/ws")
async def websocket_gateway(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
) -> None:
    """Live bidirectional WebSocket gateway for real-time telemetry, mutations, and alerts."""
    session = await ws_manager.connect(websocket, token=token)
    if not session:
        return

    try:
        while True:
            raw_message = await websocket.receive_text()
            try:
                msg = json.loads(raw_message)
            except json.JSONDecodeError:
                await ws_manager.send_to(session.client_id, {
                    "type": "error",
                    "message": "Malformed JSON payload",
                })
                continue

            action = msg.get("type", "").lower()

            if action == "ping":
                await ws_manager.send_to(session.client_id, {
                    "type": "pong",
                    "timestamp": time.time(),
                })

            elif action == "subscribe":
                requested_topics = msg.get("topics", [])
                updated = ws_manager.subscribe(session.client_id, requested_topics)
                await ws_manager.send_to(session.client_id, {
                    "type": "subscribed",
                    "topics": updated,
                })

            elif action == "unsubscribe":
                topics_to_remove = msg.get("topics", [])
                updated = ws_manager.unsubscribe(session.client_id, topics_to_remove)
                await ws_manager.send_to(session.client_id, {
                    "type": "unsubscribed",
                    "topics": updated,
                })

            elif action == "get_stats":
                snapshot = get_current_telemetry_snapshot()
                await ws_manager.send_to(session.client_id, {
                    "type": "telemetry",
                    "topic": "telemetry",
                    "data": snapshot,
                    "timestamp": time.time(),
                })

            else:
                await ws_manager.send_to(session.client_id, {
                    "type": "error",
                    "message": f"Unknown action: {action}",
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(session.client_id)
    except Exception as e:
        logger.warning(f"WebSocket session error for {session.client_id}: {e}")
        ws_manager.disconnect(session.client_id)
