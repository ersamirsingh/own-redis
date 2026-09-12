"""Unit tests for WebSocket Gateway, authentication, topic subscription, and telemetry broadcasting."""

import json
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from pyredis.api.app import create_app
from pyredis.auth.models import UserCreate
from pyredis.auth.repository import user_repo
from pyredis.auth.security import create_access_token, generate_api_key
from pyredis.core.types import Role
from pyredis.events.bus import event_bus
from pyredis.events.types import Event, EventType
from pyredis.storage.store import DataStore


@pytest.fixture(autouse=True)
def clean_state():
    user_repo.clear()
    event_bus.clear()
    yield
    user_repo.clear()
    event_bus.clear()


@pytest.fixture
def test_setup():
    store = DataStore()
    app = create_app(store=store)

    # Register admin user
    user = user_repo.create_user(
        UserCreate(email="wsadmin@pyredis.io", name="WS Admin", password="AdminSecure123!"),
        force_role=Role.ADMIN,
    )
    token = create_access_token(user.id, user.email, user.role)

    # Generate API key
    api_key_resp = user_repo.create_api_key(user.id, "Test Key", role=Role.ADMIN)
    raw_key = api_key_resp.raw_key

    return {
        "app": app,
        "store": store,
        "user": user,
        "token": token,
        "api_key": raw_key,
    }


def test_websocket_unauthorized_missing_token(test_setup):
    """WebSocket connection without token should be closed with code 1008."""
    client = TestClient(test_setup["app"])
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws"):
            pass
    assert exc_info.value.code == 1008


def test_websocket_unauthorized_invalid_token(test_setup):
    """WebSocket connection with invalid JWT token should be rejected."""
    client = TestClient(test_setup["app"])
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws?token=invalid.garbage.token"):
            pass
    assert exc_info.value.code == 1008


def test_websocket_connect_with_jwt_and_ping(test_setup):
    """Connecting with valid JWT receives welcome message and responds to ping."""
    client = TestClient(test_setup["app"])
    token = test_setup["token"]

    with client.websocket_connect(f"/ws?token={token}") as ws:
        # First message is welcome handshake
        data = ws.receive_json()
        assert data["type"] == "welcome"
        assert data["email"] == "wsadmin@pyredis.io"
        assert data["role"] == "admin"
        assert "telemetry" in data["subscribed_topics"]

        # Send ping
        ws.send_json({"type": "ping"})
        response = ws.receive_json()
        assert response["type"] == "pong"
        assert "timestamp" in response


def test_websocket_connect_with_api_key(test_setup):
    """Connecting with API key parameter is successfully authenticated."""
    client = TestClient(test_setup["app"])
    api_key = test_setup["api_key"]

    with client.websocket_connect(f"/api/ws?token={api_key}") as ws:
        welcome = ws.receive_json()
        assert welcome["type"] == "welcome"
        assert welcome["email"] == "wsadmin@pyredis.io"


def test_websocket_subscriptions(test_setup):
    """Test subscribing and unsubscribing from topics."""
    client = TestClient(test_setup["app"])
    token = test_setup["token"]

    with client.websocket_connect(f"/ws?token={token}") as ws:
        _ = ws.receive_json()  # Consume welcome

        # Subscribe to keys and traces
        ws.send_json({"type": "subscribe", "topics": ["keys", "traces"]})
        sub_resp = ws.receive_json()
        assert sub_resp["type"] == "subscribed"
        assert "keys" in sub_resp["topics"]
        assert "traces" in sub_resp["topics"]

        # Unsubscribe from keys
        ws.send_json({"type": "unsubscribe", "topics": ["keys"]})
        unsub_resp = ws.receive_json()
        assert unsub_resp["type"] == "unsubscribed"
        assert "keys" not in unsub_resp["topics"]
        assert "traces" in unsub_resp["topics"]


def test_websocket_get_stats(test_setup):
    """Test requesting immediate telemetry stats via get_stats message."""
    client = TestClient(test_setup["app"])
    token = test_setup["token"]

    with client.websocket_connect(f"/ws?token={token}") as ws:
        _ = ws.receive_json()  # Consume welcome

        ws.send_json({"type": "get_stats"})
        stats_resp = ws.receive_json()
        assert stats_resp["type"] == "telemetry"
        assert "data" in stats_resp
        assert "memory_used_bytes" in stats_resp["data"]
        assert "total_keys" in stats_resp["data"]


def test_websocket_eventbus_forwarding(test_setup):
    """Test that EventBus events are broadcast to subscribed WebSocket clients."""
    client = TestClient(test_setup["app"])
    token = test_setup["token"]

    with client.websocket_connect(f"/ws?token={token}") as ws:
        _ = ws.receive_json()  # Consume welcome

        # Subscribe to keys topic
        ws.send_json({"type": "subscribe", "topics": ["keys"]})
        _ = ws.receive_json()

        # Publish a key created event on event bus
        event_bus.publish(Event(
            type=EventType.KEY_CREATED,
            key="user:999",
            actor="wsadmin@pyredis.io",
            metadata={"type": "string"},
        ))

        # Client receives event
        event_msg = ws.receive_json()
        assert event_msg["topic"] == "keys"
        assert event_msg["type"] == "event"
        assert event_msg["event_type"] == "KEY_CREATED"
        assert event_msg["data"]["key"] == "user:999"
