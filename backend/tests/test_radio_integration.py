"""M1 integration tests (#12): the real app, the real modules, fakes only at the edges.

Real: app.main (routes, lifespan), BroadcastPlanner (#9), CatalogMusicSource (#11),
SongIntroDirector and generate_song_intro with the real prompt (#6), SpeechClient and
the audio proxy (#8, #12).
Fake: the database rows, the LLM answer and the speech service's HTTP answers. They
live only in this file (team rule: mock data only in tests). No Postgres, Gemini key,
speech service or network is needed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from contextlib import nullcontext
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.auth import optional_user
from app.content.director import SongIntroDirector
from app.content.llm import LLMClient, LLMError
from app.contracts import Track
from app.core.config import Settings
from app.main import app
from app.music.selection.base import NoTrackAvailable, TrackSelector
from app.music.source import CatalogMusicSource
from app.radio.integration import UnavailableLLM, build_llm, build_planner
from app.radio.planner import (
    BroadcastPlanner,
    PlannerSettings,
    configure_planner,
    current_planner,
)
from app.radio.planner.adapters import SpeechClientSynthesizer, speakable_emotion
from app.speech_client import PUBLIC_AUDIO_BASE, HttpSpeechClient
from app.speech_client.router import speech_http

SPEECH_URL = "http://speech.test"

CATALOG = [
    Track(
        id=f"t{i}",
        title=f"Song {i}",
        artist=f"Artist {i}",
        duration_seconds=180 + i,
        license="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        source_url=f"https://example.org/t{i}",
    )
    for i in range(1, 6)
]
BY_ID = {track.id: track for track in CATALOG}


# --- fakes at the edges -------------------------------------------------------------


class FakeDB:
    """The director looks songs up by id; none are found, so it uses the planner's info."""

    def get(self, model: Any, key: str) -> None:
        return None


class InOrderSelector(TrackSelector):
    """First catalog song that is not in the recent history (the real one is random)."""

    def __init__(self, db: Any, catalog: Sequence[Track] = CATALOG) -> None:
        self.catalog = list(catalog)

    def next_track(self, history: Sequence[Track], emotion: Any = None) -> Track:
        played = {track.id for track in history}
        for track in self.catalog:
            if track.id not in played:
                return track
        raise NoTrackAvailable("every song was played")


def fake_music(catalog: Sequence[Track] = CATALOG) -> CatalogMusicSource:
    return CatalogMusicSource(
        session_factory=lambda: nullcontext(FakeDB()),
        selector_factory=lambda db: InOrderSelector(db, catalog),
        history_loader=lambda db, ids: [BY_ID[i] for i in ids if i in BY_ID],
    )


class FakeLLM(LLMClient):
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_text(self, prompt: str, system: str | None = None) -> str:
        raise LLMError("not used")

    def generate_json(self, prompt: str, system: str | None = None) -> dict[str, Any]:
        self.prompts.append(prompt)
        return {"text": "Calm things down with this next one.", "emotion": "Calm"}


class FakeSpeechService:
    """Answers like speech/service: POST /synthesize, GET /audio/<hash>.wav, GET /health."""

    def __init__(self, fail_times: int = 0, down: bool = False) -> None:
        self.fail_times = fail_times
        self.down = down
        self.requests: list[dict] = []
        self.files: dict[str, bytes] = {}
        self.ranges: list[str | None] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        path = request.url.path
        if path == "/health":
            return httpx.Response(200, json={"status": "ok", "primary": {"engine": "fake"}})
        if path == "/synthesize":
            body = json.loads(request.content)
            self.requests.append(body)
            if self.fail_times > 0:
                self.fail_times -= 1
                return httpx.Response(503, json={"detail": "speech synthesis failed"})
            name = hashlib.sha256(request.content).hexdigest()[:32] + ".wav"
            self.files[name] = b"RIFF" + body["text"].encode()
            payload = {
                "audio_url": f"/audio/{name}",
                "duration_s": 2.5,
                "sample_rate": 24000,
                "engine": "fake",
                "cached": False,
                "loudness_lufs": None,
            }
            return httpx.Response(200, json=payload)
        if path.startswith("/audio/"):
            data = self.files.get(path.removeprefix("/audio/"))
            if data is None:
                return httpx.Response(404, json={"detail": "audio not found"})
            wanted = request.headers.get("range")
            self.ranges.append(wanted)
            headers = {"content-type": "audio/wav", "accept-ranges": "bytes"}
            if wanted == "bytes=0-3":
                headers["content-range"] = f"bytes 0-3/{len(data)}"
                return httpx.Response(206, content=data[:4], headers=headers)
            return httpx.Response(200, content=data, headers=headers)
        return httpx.Response(404)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


# --- the app with fakes --------------------------------------------------------------


@pytest.fixture
def service() -> FakeSpeechService:
    return FakeSpeechService()


def make_planner(
    service: FakeSpeechService,
    llm: LLMClient | None = None,
    music: CatalogMusicSource | None = None,
    settings: Settings | None = None,
) -> BroadcastPlanner:
    return build_planner(
        settings or Settings(_env_file=None, gemini_api_key="unused"),
        session_factory=lambda: nullcontext(FakeDB()),
        music=music or fake_music(),
        llm=llm or FakeLLM(),
        speech_client=HttpSpeechClient(
            base_url=SPEECH_URL,
            public_base_url=PUBLIC_AUDIO_BASE,
            client=httpx.AsyncClient(transport=service.transport()),
        ),
        # /next waits for the announcement, so the test does not depend on timing
        planner_settings=PlannerSettings(announcement_wait_s=5.0),
    )


@pytest.fixture
def radio(service: FakeSpeechService):
    """Starts the real app; the test configures the planner before the first request."""

    async def fake_speech_http():
        async with httpx.AsyncClient(base_url=SPEECH_URL, transport=service.transport()) as c:
            yield c

    app.dependency_overrides[optional_user] = lambda: None  # a guest listener
    app.dependency_overrides[speech_http] = fake_speech_http

    def start(planner: BroadcastPlanner) -> TestClient:
        configure_planner(planner)
        return TestClient(app)

    yield start
    configure_planner(None)
    app.dependency_overrides.clear()


def segments(client: TestClient, count: int) -> list[dict]:
    created = client.post("/api/sessions")
    assert created.status_code == 201
    session_id = created.json()["session_id"]
    result = []
    for _ in range(count):
        response = client.get(f"/api/sessions/{session_id}/next")
        assert response.status_code == 200, response.text
        result.append(response.json())
    assert client.delete(f"/api/sessions/{session_id}").status_code == 204
    return result


# --- tests ----------------------------------------------------------------------------


def test_radio_plays_song_then_voiced_intro_then_song(radio, service):
    llm = FakeLLM()
    with radio(make_planner(service, llm=llm)) as client:
        first, intro, second = (s["segment"] for s in segments(client, 3))

        assert first["kind"] == "track" and first["track_id"] == "t1"
        assert first["audio_url"] == "/api/tracks/t1/audio"  # served by #42

        assert intro["kind"] == "announcement"
        assert intro["introduces_track_id"] == "t2"
        assert intro["text"] == "Calm things down with this next one."
        assert intro["emotion"] == "calm"
        assert intro["audio_url"].startswith("/api/speech/audio/")

        assert second["kind"] == "track" and second["track_id"] == "t2"

        # the browser gets the announcement from the backend, not from the service
        audio = client.get(intro["audio_url"])
        assert audio.status_code == 200
        assert audio.headers["content-type"] == "audio/wav"
        assert audio.content == b"RIFF" + intro["text"].encode()

    # the real director built the prompt from the planner's songs
    assert '"Song 2" by Artist 2' in llm.prompts[0]
    # and the speech service got the director's decision
    spoken = service.requests[0]
    assert spoken["text"] == intro["text"] and spoken["emotion"] == "calm"


def test_without_a_gemini_key_the_template_intro_is_voiced(radio, service):
    settings = Settings(_env_file=None, gemini_api_key="")
    llm = build_llm(settings)
    assert isinstance(llm, UnavailableLLM)

    with radio(make_planner(service, llm=llm, settings=settings)) as client:
        _, intro, _ = (s["segment"] for s in segments(client, 3))

    assert intro["kind"] == "announcement"
    assert intro["text"] == "Up next, Song 2 by Artist 2."
    assert intro["emotion"] == "neutral"


def test_no_silence_while_the_speech_service_fails(radio, service):
    service.fail_times = 1  # the first announcement fails, the next one works
    with radio(make_planner(service)) as client:
        result = segments(client, 4)

    kinds = [s["segment"]["kind"] for s in result]
    assert kinds == ["track", "track", "announcement", "track"]
    assert result[1]["announcement_skipped"] == "announcement failed"
    assert [s["segment"].get("track_id") for s in result] == ["t1", "t2", None, "t3"]


def test_no_silence_when_the_speech_service_is_not_running(radio, service):
    service.down = True
    with radio(make_planner(service)) as client:
        result = segments(client, 3)
        health = client.get("/api/speech/health")

    assert [s["segment"]["kind"] for s in result] == ["track", "track", "track"]
    assert health.status_code == 503 and health.json()["status"] == "down"


def test_empty_catalog_answers_503(radio, service):
    with radio(make_planner(service, music=fake_music(catalog=[]))) as client:
        session_id = client.post("/api/sessions").json()["session_id"]
        response = client.get(f"/api/sessions/{session_id}/next")

    assert response.status_code == 503
    assert response.json()["detail"] == "No song available right now"


def test_audio_proxy_passes_range_requests_on(radio, service):
    with radio(make_planner(service)) as client:
        intro = segments(client, 2)[1]["segment"]
        partial = client.get(intro["audio_url"], headers={"Range": "bytes=0-3"})

    assert partial.status_code == 206
    assert partial.content == b"RIFF"
    assert partial.headers["content-range"].startswith("bytes 0-3/")
    assert "immutable" in partial.headers["cache-control"]
    assert service.ranges[-1] == "bytes=0-3"


@pytest.mark.parametrize(
    "name",
    ["abc.wav", "..%2Fhealth", "0123456789abcdef0123456789abcdef.mp3", "f" * 32 + ".wav"],
)
def test_audio_proxy_refuses_unknown_names(radio, service, name):
    with radio(make_planner(service)) as client:
        assert client.get(f"/api/speech/audio/{name}").status_code == 404


def test_speech_health_is_passed_on(radio, service):
    with radio(make_planner(service)) as client:
        health = client.get("/api/speech/health")
    assert health.status_code == 200 and health.json()["status"] == "ok"


def test_unknown_emotion_is_spoken_neutral():
    assert speakable_emotion(" Excited ") == "excited"
    assert speakable_emotion("angry") == "neutral"


def test_lifespan_connects_the_real_modules():
    """Without a planner from a test, starting the app wires the real parts."""
    configure_planner(None)
    with TestClient(app):  # no request: nothing touches Postgres or the speech service
        planner = current_planner()
        assert isinstance(planner, BroadcastPlanner)
        assert isinstance(planner.music, CatalogMusicSource)
        assert isinstance(planner.director, SongIntroDirector)
        assert isinstance(planner.speech, SpeechClientSynthesizer)
    assert current_planner() is None
