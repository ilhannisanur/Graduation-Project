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
    assert options.retry_options.attempts == gemini.MAX_RETRIES
    assert options.retry_options.http_status_codes == gemini.RETRY_STATUS_CODES


def test_failed_request_becomes_llm_error(monkeypatch):
    monkeypatch.setattr(gemini.genai, "Client", FakeClient)
    client = gemini.GeminiClient("key", "model")

    with pytest.raises(LLMError):
        client.generate_text("hello")
