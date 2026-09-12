"""Unit and integration tests for Phase 11: Google Gemini AI integration, semantic memory, and grounded DBA diagnostics."""

import pytest
from starlette.testclient import TestClient
from pyredis.ai.diagnostics import diagnostics_engine
from pyredis.ai.memory import semantic_memory
from pyredis.ai.provider import gemini_provider
from pyredis.api.app import create_app
from pyredis.auth.models import UserCreate
from pyredis.auth.repository import user_repo
from pyredis.auth.security import create_access_token
from pyredis.commands.registry import CommandContext, registry
from pyredis.core.types import Role
from pyredis.storage.store import DataStore


@pytest.fixture(autouse=True)
def clean_ai():
    semantic_memory.clear()
    user_repo.clear()
    yield
    semantic_memory.clear()
    user_repo.clear()


@pytest.fixture
def test_setup():
    store = DataStore()
    app = create_app(store=store)
    client = TestClient(app)

    user = user_repo.create_user(
        UserCreate(email="aiadmin@pyredis.io", name="AI Admin", password="AdminPassword123!"),
        force_role=Role.ADMIN,
    )
    token = create_access_token(user.id, user.email, user.role)
    headers = {"Authorization": f"Bearer {token}"}

    context = CommandContext(store=store, role=Role.ADMIN, session_user=user.email)

    return {
        "app": app,
        "client": client,
        "store": store,
        "user": user,
        "token": token,
        "headers": headers,
        "context": context,
    }


class TestGeminiProviderAndMemory:
    def test_provider_offline_fallbacks(self):
        # Even without an API key, fallback generation and embeddings work deterministically
        text = "PyRedis high performance cache"
        emb = gemini_provider.embed_text(text)
        assert isinstance(emb, list)
        assert len(emb) == 64
        # Norm is approx 1.0
        norm = sum(x * x for x in emb) ** 0.5
        assert round(norm, 2) == 1.0

        gen = gemini_provider.generate_text("Analyze system metrics")
        assert "PyRedis" in gen

    @pytest.mark.asyncio
    async def test_semantic_memory_crud(self):
        # 1. Add records
        id1 = await semantic_memory.add_async("Redis in-memory caching engine", metadata={"category": "db"})
        id2 = await semantic_memory.add_async("Next.js React frontend framework", metadata={"category": "ui"})
        assert semantic_memory.count() == 2

        # 2. Search query related to caching
        results = await semantic_memory.search_async("database cache", top_k=2)
        assert len(results) > 0
        assert results[0]["id"] == id1

        # 3. List
        all_entries = semantic_memory.list_entries()
        assert len(all_entries) == 2

        # 4. Delete
        assert semantic_memory.delete(id1) is True
        assert semantic_memory.count() == 1


class TestMemoryCommands:
    def test_memory_resp_commands(self, test_setup):
        ctx = test_setup["context"]

        # MEMORY.ADD
        res = registry.execute("MEMORY.ADD", ["doc:1", "High throughput distributed locking", '{"tag": "locks"}'], ctx)
        assert res == "OK"
        assert registry.execute("MEMORY.COUNT", [], ctx) == 1

        # MEMORY.SEARCH
        search_res = registry.execute("MEMORY.SEARCH", ["distributed locking", "5"], ctx)
        assert len(search_res) >= 1
        assert search_res[0][0] == "doc:1"
        assert "locks" in search_res[0][3]

        # MEMORY.DEL
        assert registry.execute("MEMORY.DEL", ["doc:1"], ctx) == 1
        assert registry.execute("MEMORY.COUNT", [], ctx) == 0


class TestDiagnosticsAndAiRoutes:
    @pytest.mark.asyncio
    async def test_diagnostics_engine(self, test_setup):
        store = test_setup["store"]
        report = await diagnostics_engine.run_diagnostics(store=store)

        assert "health_score" in report
        assert "status" in report
        assert "findings" in report
        assert "recommendations" in report
        assert "telemetry_context" in report
        assert report["health_score"] >= 0

    def test_ai_rest_endpoints(self, test_setup):
        client = test_setup["client"]
        headers = test_setup["headers"]

        # 1. Diagnostics endpoint
        diag_res = client.get("/api/ai/diagnostics", headers=headers)
        assert diag_res.status_code == 200
        data = diag_res.json()
        assert "health_score" in data
        assert "telemetry_context" in data

        # 2. Chat endpoint
        chat_payload = {
            "message": "What is the recommended eviction policy?",
            "history": [],
        }
        chat_res = client.post("/api/ai/chat", json=chat_payload, headers=headers)
        assert chat_res.status_code == 200
        chat_data = chat_res.json()
        assert "reply" in chat_data
        assert "context_used" in chat_data

        # 3. Semantic memory REST
        mem_payload = {
            "text": "Vector embeddings for AI copilot",
            "id": "mem-test-1",
            "metadata": {"source": "docs"},
        }
        add_res = client.post("/api/ai/memory", json=mem_payload, headers=headers)
        assert add_res.status_code == 200
        assert add_res.json()["id"] == "mem-test-1"

        # Search memory REST
        search_res = client.post("/api/ai/memory/search", json={"query": "AI copilot vector"}, headers=headers)
        assert search_res.status_code == 200
        assert len(search_res.json()) >= 1

        # Delete memory REST
        del_res = client.delete("/api/ai/memory/mem-test-1", headers=headers)
        assert del_res.status_code == 200

        # 4. Settings endpoint
        settings_res = client.get("/api/ai/settings", headers=headers)
        assert settings_res.status_code == 200
        s_data = settings_res.json()
        assert s_data["provider"] == "Google Gemini"

        update_res = client.post("/api/ai/settings", json={"model": "gemini-2.5-flash"}, headers=headers)
        assert update_res.status_code == 200
        assert update_res.json()["model"] == "gemini-2.5-flash"
