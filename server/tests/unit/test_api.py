"""Integration and unit tests for FastAPI Management API and RBAC enforcement."""

import httpx
import pytest
from pyredis.api.app import create_app
from pyredis.auth.models import UserCreate
from pyredis.auth.repository import user_repo
from pyredis.core.types import Role
from pyredis.storage.store import DataStore


@pytest.fixture(autouse=True)
def clean_repo():
    user_repo.clear()
    yield
    user_repo.clear()


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
    # 1. Signup user -> defaults to DEVELOPER
    signup_res = await client.post("/api/auth/signup", json={
        "email": "samir@example.com",
        "name": "Samir",
        "password": "strongPassword123!",
    })
    assert signup_res.status_code == 201
    data = signup_res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "developer"
    token = data["access_token"]

    # 2. Get /me
    me_res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "samir@example.com"
    assert me_res.json()["role"] == "developer"

    # 3. Unauthenticated /me must fail
    unauth_res = await client.get("/api/auth/me")
    assert unauth_res.status_code == 401


@pytest.mark.asyncio
async def test_keys_crud_and_rbac(client: httpx.AsyncClient) -> None:
    # 1. Seed initial Admin manually
    user_repo.create_user(
        UserCreate(email="admin_keys@example.com", name="Admin", password="password123"),
        force_role=Role.ADMIN,
    )
    admin_login = await client.post("/api/auth/login", json={
        "email": "admin_keys@example.com",
        "password": "password123",
    })
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Signup Developer user
    dev_signup = await client.post("/api/auth/signup", json={
        "email": "dev_user@example.com",
        "name": "DeveloperUser",
        "password": "password123",
    })
    assert dev_signup.status_code == 201
    assert dev_signup.json()["user"]["role"] == "developer"
    dev_id = dev_signup.json()["user"]["id"]
    dev_token = dev_signup.json()["access_token"]
    dev_headers = {"Authorization": f"Bearer {dev_token}"}

    # 3. Developer can create and read String key
    create_res = await client.post("/api/keys", json={
        "key": "app:version",
        "type": "string",
        "value": "1.0.0",
        "ttl_seconds": 3600,
    }, headers=dev_headers)
    assert create_res.status_code == 201

    get_res = await client.get("/api/keys/app:version", headers=dev_headers)
    assert get_res.status_code == 200
    assert get_res.json()["value"] == "1.0.0"

    # 4. Developer is blocked (403) from Admin-only endpoints
    snap_res = await client.post("/api/persistence/snapshot", headers=dev_headers)
    assert snap_res.status_code == 403

    # 5. Admin promotes Developer to Admin
    promote_res = await client.patch(f"/api/users/{dev_id}/role", json={
        "role": "admin",
    }, headers=admin_headers)
    assert promote_res.status_code == 200
    assert promote_res.json()["role"] == "admin"

    # 6. Promoted user logs in and can now access Admin endpoint
    promoted_login = await client.post("/api/auth/login", json={
        "email": "dev_user@example.com",
        "password": "password123",
    })
    new_admin_headers = {"Authorization": f"Bearer {promoted_login.json()['access_token']}"}
    snap_promoted = await client.post("/api/persistence/snapshot", headers=new_admin_headers)
    assert snap_promoted.status_code == 200

    # 7. Delete key
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
