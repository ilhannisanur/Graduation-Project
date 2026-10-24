from fastapi.testclient import TestClient

from app.api.dj import llm_dependency
from app.content.llm import LLMClient
from app.core.config import get_settings
from app.db.session import get_db
from app.main import app


class FakeLLM(LLMClient):
    def generate_text(self, prompt: str, system: str | None = None) -> str:
        return f"FAKE: {prompt}"

    def generate_json(self, prompt: str, system: str | None = None) -> dict:
        return {}


class FakeDB:
    def execute(self, *args, **kwargs):
        return None


class BrokenDB:
    def execute(self, *args, **kwargs):
        raise RuntimeError("db down")


SONG = {"title": "Rain", "artist": "Someone", "mood": "calm"}


def test_health_ok():
    app.dependency_overrides[get_db] = lambda: FakeDB()
    r = TestClient(app).get("/api/health")
    app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json() == {"app": "ok", "db": "up"}


def test_health_db_down():
    app.dependency_overrides[get_db] = lambda: BrokenDB()
    r = TestClient(app).get("/api/health")
    app.dependency_overrides.clear()
    assert r.json() == {"app": "ok", "db": "down"}


def test_dj_preview_uses_llm():
    app.dependency_overrides[llm_dependency] = lambda: FakeLLM()
    r = TestClient(app).post("/api/dj/preview", json=SONG)
    app.dependency_overrides.clear()
    assert r.status_code == 200
    assert "Rain" in r.json()["announcement"]


def test_dj_preview_without_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    r = TestClient(app).post("/api/dj/preview", json=SONG)
    get_settings.cache_clear()
    assert r.status_code == 503
