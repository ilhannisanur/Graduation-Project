import pytest
from fastapi.testclient import TestClient

from app.api.dj import llm_dependency
from app.content.llm import LLMClient, LLMError
from app.main import app

URL = "/api/dj/song-intro-preview"
BODY = {"next_track": {"title": "Rain", "artist": "Someone", "valence": 0.3, "arousal": 0.2}}


class AnswerLLM(LLMClient):
    """Returns the same JSON answer every time and counts the calls."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    def generate_text(self, prompt: str, system: str | None = None) -> str:
        raise AssertionError("song intro must use generate_json")

    def generate_json(self, prompt: str, system: str | None = None) -> dict:
        self.calls += 1
        return self.answer


class FailingLLM(AnswerLLM):
    def generate_json(self, prompt: str, system: str | None = None) -> dict:
        self.calls += 1
        raise LLMError("timeout")


@pytest.fixture
def post():
    def _post(llm: LLMClient, body: dict = BODY):
        app.dependency_overrides[llm_dependency] = lambda: llm
        try:
            return TestClient(app).post(URL, json=body)
        finally:
            app.dependency_overrides.clear()

    return _post


def test_valid_answer_is_returned_with_timing(post):
    llm = AnswerLLM({"text": "Here comes Rain by Someone, nice and slow.", "emotion": "Calm"})
    r = post(llm)
    assert r.status_code == 200
    data = r.json()
    assert data["text"] == "Here comes Rain by Someone, nice and slow."
    assert data["emotion"] == "calm"
    assert data["used_fallback"] is False
    assert data["target_seconds"] > 0
    assert '"Rain" by Someone' in data["prompt"]
    assert "Valence: 0.30, arousal: 0.20" in data["prompt"]
    assert len(data["llm_calls"]) == 1
    assert data["llm_calls"][0]["ok"] is True
    assert data["llm_ms"] == data["llm_calls"][0]["duration_ms"] >= 0


def test_llm_error_gives_fallback(post):
    llm = FailingLLM(None)
    data = post(llm).json()
    assert data["used_fallback"] is True
    assert data["text"] == "Up next, Rain by Someone."
    assert data["emotion"] == "neutral"
    assert llm.calls == 1  # LLMError is not retried again here; the client already retried
    assert [call["ok"] for call in data["llm_calls"]] == [False]


def test_unusable_answer_is_retried_once_then_fallback(post):
    llm = AnswerLLM({"text": "Hi", "emotion": "furious"})
    data = post(llm).json()
    assert data["used_fallback"] is True
    assert llm.calls == 2
    assert [call["ok"] for call in data["llm_calls"]] == [True, True]
    assert data["llm_ms"] == sum(call["duration_ms"] for call in data["llm_calls"])


def test_recent_announcements_go_into_prompt(post):
    body = {**BODY, "recent_announcements": ["First one.", "Second one."]}
    llm = AnswerLLM({"text": "Rain is up next.", "emotion": "calm"})
    prompt = post(llm, body).json()["prompt"]
    assert "1. First one." in prompt
    assert "2. Second one." in prompt


def test_previous_track_is_accepted(post):
    body = {**BODY, "previous_track": {"title": "Sun", "artist": "Other"}}
    llm = AnswerLLM({"text": "Rain is up next.", "emotion": "calm"})
    assert post(llm, body).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"next_track": {"title": "", "artist": "Someone"}},
        {"next_track": {"title": "Rain"}},
        {"next_track": {"title": "Rain", "artist": "Someone", "valence": 1.5}},
        {**BODY, "recent_announcements": ["a", "b", "c", "d"]},
    ],
)
def test_invalid_request_is_rejected(post, body):
    llm = AnswerLLM({})
    assert post(llm, body).status_code == 422
    assert llm.calls == 0
