"""Integration and unit tests for FastAPI Management API and RBAC enforcement."""

import httpx
import pytest
from pyredis.api.app import create_app
from pyredis.auth.repository import user_repo
from pyredis.core.types import Role
from pyredis.storage.store import DataStore


@pytest.fixture
def app():
    # Fresh store for API tests
    store = DataStore()
    return create_app(store=store)


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health_check(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "pyredis"}


@pytest.mark.asyncio
async def test_auth_signup_and_me(client: httpx.AsyncClient) -> None:
    # 1. Signup first user -> Admin
    signup_res = await client.post("/api/auth/signup", json={
        "email": "samir@example.com",
        "name": "Samir",
        "password": "strongPassword123!",
    })
    assert signup_res.status_code == 201
    data = signup_res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "admin"
    token = data["access_token"]

    # 2. Get /me
    me_res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "samir@example.com"

    # 3. Unauthenticated /me must fail
    unauth_res = await client.get("/api/auth/me")
    assert unauth_res.status_code == 401


@pytest.mark.asyncio
async def test_keys_crud_and_rbac(client: httpx.AsyncClient) -> None:
    # 1. Signup Admin
    admin_signup = await client.post("/api/auth/signup", json={
        "email": "admin_keys@example.com",
        "name": "Admin",
        "password": "password123",
    })
    admin_token = admin_signup.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Signup ReadOnly user
    ro_signup = await client.post("/api/auth/signup", json={
        "email": "ro_user@example.com",
        "name": "ReadOnlyUser",
        "password": "password123",
        "role": "readonly",
    })
    ro_token = ro_signup.json()["access_token"]
    ro_headers = {"Authorization": f"Bearer {ro_token}"}

    # 3. Admin creates String key
    create_res = await client.post("/api/keys", json={
        "key": "app:version",
        "type": "string",
        "value": "1.0.0",
        "ttl_seconds": 3600,
    }, headers=admin_headers)
    assert create_res.status_code == 201

    # 4. ReadOnly user can read key
    get_res = await client.get("/api/keys/app:version", headers=ro_headers)
    assert get_res.status_code == 200
    assert get_res.json()["value"] == "1.0.0"

    # 5. ReadOnly user is blocked (403) from creating or deleting keys
    ro_create = await client.post("/api/keys", json={
        "key": "hack",
        "type": "string",
        "value": "bad",
    }, headers=ro_headers)
    assert ro_create.status_code == 403

    ro_del = await client.delete("/api/keys/app:version", headers=ro_headers)
    assert ro_del.status_code == 403

    # 6. Admin can delete key
    admin_del = await client.delete("/api/keys/app:version", headers=admin_headers)
    assert admin_del.status_code == 204


@pytest.mark.asyncio
async def test_command_console_route(client: httpx.AsyncClient) -> None:
    # 1. Login/signup
    signup = await client.post("/api/auth/signup", json={
        "email": "console_user@example.com",
        "name": "ConsoleDev",
        "password": "password123",
    })
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Execute SET
    set_res = await client.post("/api/commands", json={
        "command": 'SET greeting "Hello from Web Console"',
    }, headers=headers)
    assert set_res.status_code == 200
    assert set_res.json()["result"] == "OK"

    # 3. Execute GET
    get_res = await client.post("/api/commands", json={
        "command": "GET greeting",
    }, headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["result"] == "Hello from Web Console"


@pytest.mark.asyncio
async def test_api_key_authentication(client: httpx.AsyncClient) -> None:
    # 1. Signup user
    signup = await client.post("/api/auth/signup", json={
        "email": "service@example.com",
        "name": "Service",
        "password": "password123",
    })
    token = signup.json()["access_token"]

    # 2. Create API key
    key_res = await client.post("/api/auth/api-keys", json={
        "name": "Microservice Token",
        "role": "developer",
    }, headers={"Authorization": f"Bearer {token}"})
    assert key_res.status_code == 201
    raw_key = key_res.json()["raw_key"]
    assert raw_key is not None

    # 3. Use raw API key in Authorization header
    api_headers = {"Authorization": f"Bearer {raw_key}"}
    stats_res = await client.get("/api/stats", headers=api_headers)
    assert stats_res.status_code == 200
    assert "uptime_seconds" in stats_res.json()
