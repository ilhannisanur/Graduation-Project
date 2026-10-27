"""Tests for the broadcast planner (#9).

Acceptance criteria of the issue:
* end-to-end flow tested with fake services  -> test_api_end_to_end_with_fake_services
* no silence, shown by a test                  -> test_no_silence_*

Fake services live only in this file (team rule: mock data only in tests).
"""

from __future__ import annotations

import asyncio
import itertools
import time
from collections.abc import Sequence
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import optional_user
from app.radio.planner import (
    AnnouncementPlan,
    AnnouncementRequest,
    BroadcastPlanner,
    NoTrackAvailable,
    PlannerSettings,
    SessionNotFound,
    SpeechAudio,
    TrackInfo,
    get_planner,
    router,
)
from app.radio.planner.adapters import HttpSpeechSynthesizer
from app.users import UserRow

# --- fakes ----------------------------------------------------------------------------

CATALOG = [
    TrackInfo(
        track_id=f"t{i}",
        title=f"Song {i}",
        artist=f"Artist {i}",
        duration_s=180 + i,
        license="CC BY 4.0",
    )
    for i in range(1, 9)
]


class FakeMusic:
    def __init__(
        self, catalog: Sequence[TrackInfo] = CATALOG, fail_after: int | None = None
    ) -> None:
        self.catalog = list(catalog)
        self.calls = 0
        self.fail_after = fail_after

    async def next_track(self, *, user_id: str, recent_track_ids: Sequence[str]) -> TrackInfo:
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise ConnectionError("music database down")
        for track in self.catalog:
            if track.track_id not in recent_track_ids:
                return track
        return self.catalog[0]


class FakeDirector:
    def __init__(self) -> None:
        self.requests: list[AnnouncementRequest] = []

    async def plan(self, request: AnnouncementRequest) -> AnnouncementPlan:
        self.requests.append(request)
        nxt = request.next_track
        return AnnouncementPlan(
            text=f"Up next: {nxt.title} by {nxt.artist}.", emotion="calm", intensity=0.6
        )


class FakeSpeech:
    def __init__(self, delay_s: float = 0.0, fail: bool = False) -> None:
        self.delay_s = delay_s
        self.fail = fail
        self.calls = 0

    async def synthesize(self, plan: AnnouncementPlan) -> SpeechAudio:
        self.calls += 1
        await asyncio.sleep(self.delay_s)
        if self.fail:
            raise RuntimeError("speech service crashed")
        return SpeechAudio(audio_url=f"/speech/{self.calls}.wav", duration_s=len(plan.text) / 15)


def make_planner(
    speech: FakeSpeech | None = None, music: FakeMusic | None = None, **settings
) -> BroadcastPlanner:
    settings.setdefault(
        "announcement_wait_s", 1.0
    )  # fast fakes: wait so the order is deterministic
    settings.setdefault("music_timeout_s", 0.5)
    return BroadcastPlanner(
        music=music or FakeMusic(),
        director=FakeDirector(),
        speech=speech or FakeSpeech(),
        settings=PlannerSettings(**settings),
    )


async def take(planner: BroadcastPlanner, session_id: str, n: int) -> list:
    return [await planner.next_segment(session_id) for _ in range(n)]


def kinds(responses) -> list[str]:
    return [r.segment.kind for r in responses]


def assert_valid_order(responses) -> None:
    """Every announcement is followed by the song it introduces; no empty segment."""
    for i, r in enumerate(responses):
        seg = r.segment
        assert seg.audio_url and seg.duration_s > 0
        assert r.position == i + 1
        if seg.kind == "announcement" and i + 1 < len(responses):
            nxt = responses[i + 1].segment
            assert nxt.kind == "track" and nxt.track_id == seg.introduces_track_id


# --- order of the broadcast -----------------------------------------------------------


def test_song_announcement_song_order():
    async def scenario():
        planner = make_planner()
        session = planner.create_session("u1")
        out = await take(planner, session.session_id, 7)
        await planner.aclose()
        return out, planner

    out, planner = asyncio.run(scenario())
    assert kinds(out) == [
        "track",
        "announcement",
        "track",
        "announcement",
        "track",
        "announcement",
        "track",
    ]
    assert_valid_order(out)
    tracks = [r.segment.track_id for r in out if r.segment.kind == "track"]
    assert len(set(tracks)) == len(tracks), "no song repeats within the recent history"
    assert out[0].segment.audio_url == "/api/tracks/t1/audio"
    # the director gets the previous and the next song, and nothing about the user
    request = planner.director.requests[0]
    assert request.previous_track.track_id == "t1" and request.next_track.track_id == "t2"
    assert "user" not in request.model_dump_json()


def test_two_songs_between_announcements():
    async def scenario():
        planner = make_planner(songs_per_announcement=2)
        session = planner.create_session()
        out = await take(planner, session.session_id, 7)
        await planner.aclose()
        return out

    out = asyncio.run(scenario())
    assert kinds(out) == [
        "track",
        "track",
        "announcement",
        "track",
        "track",
        "announcement",
        "track",
    ]
    assert_valid_order(out)


def test_next_block_is_prepared_in_the_background():
    async def scenario():
        planner = make_planner(speech=FakeSpeech(delay_s=0.05), announcement_wait_s=0.0)
        session = planner.create_session()
        await planner.next_segment(session.session_id)  # song 1 starts playing
        await asyncio.sleep(0.2)  # ... while it plays, the announcement is prepared
        started = time.perf_counter()
        second = await planner.next_segment(session.session_id)
        elapsed = time.perf_counter() - started
        await planner.aclose()
        return second, elapsed

    second, elapsed = asyncio.run(scenario())
    assert second.segment.kind == "announcement" and second.announcement_skipped is None
    assert elapsed < 0.05, "a prepared segment is returned without waiting"


# --- no silence (acceptance criterion) ------------------------------------------------


def test_no_silence_when_speech_is_slow():
    """A listener asks for the next segment the moment the current one ends.

    The speech service needs 5 s per announcement, but /next must never make
    the listener wait: the gap between two segments stays far below a second,
    and the song is played instead of the unfinished announcement.
    """

    async def scenario():
        planner = make_planner(speech=FakeSpeech(delay_s=5.0), announcement_wait_s=0.05)
        session = planner.create_session()
        gaps, out = [], []
        for _ in range(8):
            started = time.perf_counter()
            out.append(await planner.next_segment(session.session_id))
            gaps.append(time.perf_counter() - started)
        await planner.aclose()
        return out, gaps

    out, gaps = asyncio.run(scenario())
    assert max(gaps) < 0.3, f"listener waited {max(gaps):.2f} s between segments"
    assert kinds(out) == ["track"] * 8
    assert all(r.announcement_skipped == "announcement not ready" for r in out[1:])
    assert_valid_order(out)


def test_no_silence_when_speech_fails():
    async def scenario():
        planner = make_planner(speech=FakeSpeech(fail=True))
        session = planner.create_session()
        out = await take(planner, session.session_id, 5)
        await planner.aclose()
        return out

    out = asyncio.run(scenario())
    assert kinds(out) == ["track"] * 5
    assert all(r.announcement_skipped == "announcement failed" for r in out[1:])


def test_no_silence_when_music_source_fails():
    """After 3 songs the music database goes down: recent songs are replayed."""

    async def scenario():
        planner = make_planner(music=FakeMusic(fail_after=3))
        session = planner.create_session()
        out = await take(planner, session.session_id, 9)
        await planner.aclose()
        return out

    out = asyncio.run(scenario())
    tracks = [r.segment.track_id for r in out if r.segment.kind == "track"]
    assert len(tracks) == 5
    assert set(tracks[3:]) <= set(tracks[:3]), "replayed songs come from the history"
    assert all(a != b for a, b in itertools.pairwise(tracks)), "never the same song twice in a row"
    assert_valid_order(out)


def test_no_track_at_all_is_reported():
    async def scenario():
        planner = make_planner(music=FakeMusic(fail_after=0))
        session = planner.create_session()
        with pytest.raises(NoTrackAvailable):
            await planner.next_segment(session.session_id)
        await planner.aclose()

    asyncio.run(scenario())


# --- sessions -------------------------------------------------------------------------


def test_concurrent_requests_do_not_skip_segments():
    async def scenario():
        planner = make_planner()
        session = planner.create_session()
        out = await asyncio.gather(*(planner.next_segment(session.session_id) for _ in range(5)))
        await planner.aclose()
        return sorted(out, key=lambda r: r.position)

    out = asyncio.run(scenario())
    assert [r.position for r in out] == [1, 2, 3, 4, 5]
    assert_valid_order(out)


def test_sessions_are_independent_and_expire():
    async def scenario():
        planner = make_planner(session_ttl_s=0.1)
        a, b = planner.create_session("a"), planner.create_session("b")
        first_a = await planner.next_segment(a.session_id)
        first_b = await planner.next_segment(b.session_id)
        await asyncio.sleep(0.2)
        planner.create_session("c")  # triggers clean-up of idle sessions
        with pytest.raises(SessionNotFound):
            await planner.next_segment(a.session_id)
        count = planner.session_count
        await planner.aclose()
        return first_a, first_b, count

    first_a, first_b, count = asyncio.run(scenario())
    # each listener has its own queue
    assert first_a.segment.track_id == first_b.segment.track_id == "t1"
    assert first_a.position == first_b.position == 1
    assert count == 1


def test_close_user_sessions_closes_only_that_users_sessions():
    planner = make_planner()
    mine = [planner.create_session(user_id="usr_a") for _ in range(2)]
    other = planner.create_session(user_id="usr_b")

    assert planner.close_user_sessions("usr_a") == 2

    for session in mine:
        with pytest.raises(SessionNotFound):
            planner.get_session(session.session_id)
    assert planner.get_session(other.session_id) is other


def test_settings_validation():
    with pytest.raises(ValueError):
        PlannerSettings(songs_per_announcement=0)


# --- HTTP API end to end (acceptance criterion) ---------------------------------------


def make_app(planner: BroadcastPlanner | None) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    if planner is not None:
        app.dependency_overrides[get_planner] = lambda: planner
    return app


def test_api_end_to_end_with_fake_services():
    planner = make_planner()
    with TestClient(make_app(planner)) as client:  # one event loop for all requests
        created = client.post("/api/sessions")
        assert created.status_code == 201
        assert created.json()["user_id"] == "guest"
        session_id = created.json()["session_id"]

        responses = []
        for _ in range(5):
            r = client.get(f"/api/sessions/{session_id}/next")
            assert r.status_code == 200
            responses.append(r.json())

        assert [r["segment"]["kind"] for r in responses] == [
            "track",
            "announcement",
            "track",
            "announcement",
            "track",
        ]
        announcement, track = responses[1]["segment"], responses[2]["segment"]
        assert announcement["introduces_track_id"] == track["track_id"]
        assert announcement["text"].startswith("Up next")
        assert track["audio_url"] == f"/api/tracks/{track['track_id']}/audio"
        assert {"title", "artist", "license", "duration_s"} <= set(track)

        assert client.get("/api/sessions/unknown/next").status_code == 404
        assert client.delete(f"/api/sessions/{session_id}").status_code == 204
        assert client.get(f"/api/sessions/{session_id}/next").status_code == 404


class LoggedIn:
    """Stands in for the login cookie: tests switch who is logged in between requests."""

    def __init__(self) -> None:
        self.user: UserRow | None = None

    def as_(self, user_id: str | None) -> None:
        self.user = UserRow(id=user_id, username=user_id) if user_id else None


def make_app_with_login(planner: BroadcastPlanner) -> tuple[FastAPI, LoggedIn]:
    app = make_app(planner)
    login = LoggedIn()
    app.dependency_overrides[optional_user] = lambda: login.user
    return app, login


def test_session_user_comes_from_the_login_not_the_request():
    app, login = make_app_with_login(make_planner())
    with TestClient(app) as client:
        login.as_("usr_azra")
        created = client.post("/api/sessions", json={"user_id": "usr_victim"})
        assert created.json()["user_id"] == "usr_azra"

        login.as_(None)
        guest = client.post("/api/sessions", json={"user_id": "usr_victim"})
        assert guest.json()["user_id"] == "guest"


def test_an_accounts_session_is_closed_to_others():
    app, login = make_app_with_login(make_planner())
    with TestClient(app) as client:
        login.as_("usr_azra")
        session_id = client.post("/api/sessions").json()["session_id"]

        for other in ["usr_nisa", None]:  # another account, then a guest
            login.as_(other)
            assert client.get(f"/api/sessions/{session_id}/next").status_code == 404
            assert client.delete(f"/api/sessions/{session_id}").status_code == 404

        login.as_("usr_azra")
        assert client.get(f"/api/sessions/{session_id}/next").status_code == 200
        assert client.delete(f"/api/sessions/{session_id}").status_code == 204


def test_guest_session_works_with_or_without_login():
    app, login = make_app_with_login(make_planner())
    with TestClient(app) as client:
        session_id = client.post("/api/sessions").json()["session_id"]

        login.as_("usr_nisa")  # logging in later does not lock the listener out
        assert client.get(f"/api/sessions/{session_id}/next").status_code == 200


def test_real_login_cookie_owns_the_session(db_session):
    # The whole app with a real account and cookie (needs Postgres; skipped without it).
    from app.db.session import get_db
    from app.main import app

    planner = make_planner()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_planner] = lambda: planner
    try:
        with TestClient(app) as client:
            name = f"test_{uuid4().hex[:12]}"
            user = client.post(
                "/api/auth/register", json={"username": name, "password": "a long password"}
            ).json()

            created = client.post("/api/sessions", json={"user_id": "usr_victim"}).json()
            assert created["user_id"] == user["id"]
            session_id = created["session_id"]
            assert client.get(f"/api/sessions/{session_id}/next").status_code == 200

            client.post("/api/auth/logout")
            assert client.get(f"/api/sessions/{session_id}/next").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_api_reports_503_when_not_wired_or_no_music():
    with TestClient(make_app(None)) as client:
        assert client.post("/api/sessions").status_code == 503

    planner = make_planner(music=FakeMusic(fail_after=0))
    with TestClient(make_app(planner)) as client:
        session_id = client.post("/api/sessions").json()["session_id"]
        assert client.get(f"/api/sessions/{session_id}/next").status_code == 503


# --- speech adapter -------------------------------------------------------------------


def test_http_speech_synthesizer_against_a_fake_server():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"audio_url": "/audio/abc.wav", "duration_s": 7.5})

    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        speech = HttpSpeechSynthesizer(
            "http://speech:8001", public_base_url="http://localhost:8001", client=client
        )
        audio = await speech.synthesize(
            AnnouncementPlan(text="Hello Ankara", emotion="happy", intensity=0.8)
        )
        await speech.aclose()
        return audio

    audio = asyncio.run(scenario())
    assert seen["url"] == "http://speech:8001/synthesize"
    assert '"emotion":"happy"' in seen["body"].replace(" ", "")
    assert audio.audio_url == "http://localhost:8001/audio/abc.wav" and audio.duration_s == 7.5
