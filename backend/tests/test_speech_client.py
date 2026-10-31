"""SpeechClient tests (#8).

The fake client and the fake HTTP server below live only in this test file
(team rule: mock data only in tests). No speech service or model is needed.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.speech_client import (
    HttpSpeechClient,
    SpeechClient,
    SpeechRequest,
    SpeechResult,
    SpeechServiceError,
    get_speech_client,
)


class FakeSpeechClient:
    """Stands in for the speech service in backend tests."""

    def __init__(self, fail: bool = False) -> None:
        self.requests: list[SpeechRequest] = []
        self.fail = fail

    async def synthesize(self, request: SpeechRequest) -> SpeechResult:
        self.requests.append(request)
        if self.fail:
            raise SpeechServiceError("speech service returned 503: all engines failed")
        return SpeechResult(
            audio_url=f"http://speech.test/audio/{len(self.requests):032d}.wav",
            duration_s=round(len(request.text) / 15, 2),
            sample_rate=24_000,
            engine="fake",
        )

    async def health(self) -> dict:
        return {"status": "ok"}


def run(coro):
    return asyncio.run(coro)


def http_client(handler) -> HttpSpeechClient:
    return HttpSpeechClient(
        base_url="http://speech:8001",
        public_base_url="http://localhost:8001",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def test_fake_client_satisfies_the_interface():
    fake: SpeechClient = FakeSpeechClient()
    result = run(fake.synthesize(SpeechRequest(text="Hello Ankara", emotion="happy")))
    assert result.engine == "fake" and result.audio_url.endswith(".wav")


def test_a_route_can_use_the_fake_client():
    """How backend tests replace the real service: override the dependency."""
    app = FastAPI()

    @app.post("/demo")
    async def demo(client: SpeechClient = Depends(get_speech_client)) -> dict:  # noqa: B008
        result = await client.synthesize(SpeechRequest(text="Up next, a calm one.", emotion="calm"))
        return {"audio": result.audio_url}

    fake = FakeSpeechClient()
    app.dependency_overrides[get_speech_client] = lambda: fake
    with TestClient(app) as client:
        assert client.post("/demo").json()["audio"].startswith("http://speech.test/audio/")
    assert fake.requests[0].emotion == "calm"


def test_http_client_sends_the_request_and_makes_the_url_absolute():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        payload = {
            "audio_url": "/audio/ab.wav",
            "duration_s": 2.5,
            "sample_rate": 24000,
            "engine": "orpheus-hf",
            "cached": False,
            "loudness_lufs": None,
        }
        return httpx.Response(200, json=payload)

    client = http_client(handler)
    result = run(client.synthesize(SpeechRequest(text="Hi", emotion="sad", intensity=0.8)))
    run(client.aclose())
    assert seen["url"] == "http://speech:8001/synthesize"
    assert seen["body"]["emotion"] == "sad" and seen["body"]["intensity"] == 0.8
    assert result.audio_url == "http://localhost:8001/audio/ab.wav"
    assert result.engine == "orpheus-hf" and result.duration_s == 2.5


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(503, json={"detail": "speech synthesis failed"}), "503"),
        (httpx.Response(422, json={"detail": "unknown voice_id"}), "unknown voice_id"),
        (httpx.Response(500, text="Internal Server Error"), "500"),
    ],
)
def test_http_client_turns_service_errors_into_one_exception(response, message):
    client = http_client(lambda request: response)
    with pytest.raises(SpeechServiceError, match=message):
        run(client.synthesize(SpeechRequest(text="Hi")))


def test_http_client_reports_an_unreachable_service():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(SpeechServiceError, match="unreachable"):
        run(http_client(handler).health())


def test_request_validation_matches_the_service():
    with pytest.raises(ValueError):
        SpeechRequest(text="")
    with pytest.raises(ValueError):
        SpeechRequest(text="hi", emotion="angry")
    with pytest.raises(ValueError):
        SpeechRequest(text="hi", intensity=2)


def test_get_speech_client_reads_the_address(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SPEECH_SERVICE_URL", "http://gpu-box:8001/")
    client = get_speech_client()
    assert isinstance(client, HttpSpeechClient) and client.base_url == "http://gpu-box:8001"
