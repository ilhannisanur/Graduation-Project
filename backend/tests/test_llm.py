import pytest

from app.content.llm import gemini
from app.content.llm.base import LLMError

created_with: list[dict] = []  # settings that GeminiClient passed to genai.Client


class FakeInteractions:
    def create(self, **params):
        raise RuntimeError("boom")


class FakeClient:
    """Stands in for genai.Client: remembers its settings, never calls the network."""

    def __init__(self, **kwargs):
        created_with.append(kwargs)
        self.interactions = FakeInteractions()


def test_client_gets_timeout_and_retry_limit(monkeypatch):
    created_with.clear()
    monkeypatch.setattr(gemini.genai, "Client", FakeClient)

    gemini.GeminiClient("key", "model")

    options = created_with[0]["http_options"]
    assert options.timeout == gemini.TIMEOUT_MS
    assert options.retry_options.attempts == gemini.MAX_RETRIES + 1
    assert options.retry_options.http_status_codes == gemini.RETRY_STATUS_CODES


class Answer:
    output_text = "hi"


class BusyFirstModel:
    """The first model is "busy"; any other model answers. Remembers the models asked."""

    def __init__(self) -> None:
        self.models: list[str] = []

    def create(self, **params):
        self.models.append(params["model"])
        if params["model"] == "main":
            raise RuntimeError("503 high demand")
        return Answer()


def test_fallback_model_answers_when_the_main_one_is_busy(monkeypatch):
    monkeypatch.setattr(gemini.genai, "Client", FakeClient)
    client = gemini.GeminiClient("key", "main", ["spare", "last"])
    client._client.interactions = busy = BusyFirstModel()

    assert client.generate_text("hello") == "hi"
    assert busy.models == ["main", "spare"]


def test_all_models_failing_is_one_llm_error_naming_each(monkeypatch):
    monkeypatch.setattr(gemini.genai, "Client", FakeClient)
    client = gemini.GeminiClient("key", "main", ["spare"])

    with pytest.raises(LLMError, match="main: boom.*spare: boom"):
        client.generate_text("hello")


def test_failed_request_becomes_llm_error(monkeypatch):
    monkeypatch.setattr(gemini.genai, "Client", FakeClient)
    client = gemini.GeminiClient("key", "model")

    with pytest.raises(LLMError):
        client.generate_text("hello")
