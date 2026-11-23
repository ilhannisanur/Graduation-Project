import asyncio
import random
import uuid
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.content.director.song_intro_director import shoutout_plan, shoutout_text
from app.contracts import Track
from app.db.session import get_db
from app.main import app
from app.music import TrackRow
from app.music.broadcast_source import BroadcastMusicSource
from app.music.mood_target import PRESETS, choose_for_target, set_target
from app.music.requests import SongRequestRow, service
from app.radio.planner import AnnouncementPlan, RequestNote
from app.users import UserRow

PASSWORD = "correct horse battery"


def track(n: int, valence: float | None, energy: float | None) -> Track:
    return Track(
        id=f"t{n}",
        title=f"Song {n}",
        artist=f"Artist {n}",
        duration_seconds=100,
        license="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        source_url="https://example.org",
        valence=valence,
        arousal=energy,
    )


@pytest.fixture(autouse=True)
def no_mood():
    set_target(None)
    yield
    set_target(None)


@pytest.fixture(autouse=True)
def empty_queue(request):
    """Real requests in the shared developer database are marked played inside the test's
    transaction (rolled back afterwards), so the queue starts empty."""
    if "db_session" in request.fixturenames:
        db = request.getfixturevalue("db_session")
        db.execute(
            update(SongRequestRow)
            .where(SongRequestRow.status == "accepted")
            .values(status="played")
        )


# ------------------------------------------------------------------------ no database


def test_target_picks_one_of_the_closest_songs():
    calm = PRESETS["calm"]
    near = [track(i, calm.valence + i / 100, calm.energy) for i in range(6)]
    far = [track(10 + i, 0.1, 0.95) for i in range(10)]

    for seed in range(20):
        assert choose_for_target(far + near, [], calm, random.Random(seed)) in near


def test_target_skips_recent_songs_and_songs_without_values():
    calm = PRESETS["calm"]
    songs = [track(1, calm.valence, calm.energy), track(2, 0.5, 0.5), track(3, None, None)]

    assert choose_for_target(songs, ["t1"], calm, random.Random(0)).id == "t2"
    assert choose_for_target([track(3, None, None)], [], calm, random.Random(0)) is None


def test_shoutout_names_and_message():
    one = shoutout_text(RequestNote(on_air_names=["Hakan"], messages=["Good luck, team!"]))
    many = shoutout_text(RequestNote(on_air_names=["Ada", "Can", "Ece"]))

    assert one == (
        'This one goes out to Hakan, who asked for it. The message says: "Good luck, team."'
    )
    assert many == "This one goes out to Ada, Can and Ece."
    assert shoutout_text(RequestNote()) == "This one is a listener request."


def test_request_is_announced_with_a_short_happy_shoutout():
    out = shoutout_plan(RequestNote(on_air_names=["Hakan"]), "Song 1", "Artist 1")

    assert out == AnnouncementPlan(
        text="This one goes out to Hakan, who asked for it. Here is Song 1 by Artist 1.",
        emotion="happy",
        intensity=0.4,
    )


def test_moods_are_listed_and_setting_one_needs_a_login():
    client = TestClient(app)

    body = client.get("/api/station/moods").json()

    assert {m["id"] for m in body["presets"]} == set(PRESETS)
    assert body["current"] is None
    assert client.post("/api/station/mood", json={"id": "calm"}).status_code == 401


def test_station_info_gives_the_request_page():
    assert TestClient(app).get("/api/station/info").json()["request_url"].endswith("/#/request")


def test_unknown_emotion_sample_is_not_served():
    assert TestClient(app).get("/api/station/emotions/..%2F..%2F.env").status_code == 404


# ------------------------------------------------------------------------- database


@pytest.fixture
def client(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_track(db: Session, valence: float = 0.5, energy: float = 0.5) -> TrackRow:
    row = TrackRow(
        id=f"trk_st_{uuid.uuid4().hex[:10]}",
        title="Station Song",
        artist="Some Artist",
        duration_seconds=100.0,
        license="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        source_url="https://example.org",
        valence=valence,
        arousal=energy,
        source="test-station",
        source_track_id=uuid.uuid4().hex[:10],
    )
    db.add(row)
    db.flush()
    return row


def make_user(db: Session) -> UserRow:
    user = UserRow(username=f"test_{uuid.uuid4().hex[:12]}", password_hash="x")
    db.add(user)
    db.flush()
    return user


def source_for(db: Session) -> BroadcastMusicSource:
    """The source uses the test's own session; its commit stays inside the test's savepoint."""

    @contextmanager
    def factory():
        yield db

    return BroadcastMusicSource(factory)


def test_logged_in_user_sets_the_mood(client: TestClient):
    name = f"test_{uuid.uuid4().hex[:12]}"
    client.post("/api/auth/register", json={"username": name, "password": PASSWORD})

    body = client.post("/api/station/mood", json={"id": "rainy-evening"}).json()

    assert body["current"]["id"] == "rainy-evening"
    assert client.post("/api/station/mood", json={"id": "nope"}).status_code == 404
    assert client.post("/api/station/mood", json={"id": None}).json()["current"] is None


def test_map_lists_tracks_with_values(client: TestClient, db_session: Session):
    row = make_track(db_session, 0.2, 0.8)

    points = {p["id"]: p for p in client.get("/api/station/map").json()}

    assert (points[row.id]["valence"], points[row.id]["energy"]) == (0.2, 0.8)


def test_public_queue_shows_names_but_no_user_ids(client: TestClient, db_session: Session):
    a, b = make_user(db_session), make_user(db_session)
    song = make_track(db_session)
    service.create_request(db_session, a.id, "x", song.id, on_air_name="Hakan")
    service.create_request(db_session, b.id, "y", song.id)

    queue = client.get("/api/requests/queue").json()

    item = next(i for i in queue if i["track_id"] == song.id)
    assert (item["requests"], item["on_air_names"], item["messages"]) == (2, ["Hakan"], [])
    assert a.id not in str(queue) and b.id not in str(queue)


def test_request_api_takes_name_and_message(client: TestClient, db_session: Session):
    name = f"test_{uuid.uuid4().hex[:12]}"
    client.post("/api/auth/register", json={"username": name, "password": PASSWORD})
    song = make_track(db_session)

    body = client.post(
        "/api/requests",
        json={
            "raw_text": "Good luck!",
            "track_id": song.id,
            "on_air_name": " Hakan ",
            "message": "Good luck!",
            "message_readout_allowed": True,
        },
    ).json()

    assert body["intent"]["message"] == "Good luck!"
    assert body["intent"]["song_title"] == "Station Song"
    row = db_session.get(SongRequestRow, body["id"])
    assert row.on_air_name == "Hakan"


def test_broadcast_source_plays_requests_first_with_the_shoutout_note(db_session: Session):
    user = make_user(db_session)
    song = make_track(db_session)
    service.create_request(
        db_session,
        user.id,
        "for the class",
        song.id,
        message_readout_allowed=True,
        on_air_name="Hakan",
        message="Good luck!",
    )

    source = source_for(db_session)

    info = asyncio.run(source.next_track(user_id="guest", recent_track_ids=[]))

    assert info.track_id == song.id
    assert info.reason == "Requested by Hakan"
    assert info.request == RequestNote(on_air_names=["Hakan"], messages=["Good luck!"])
    status = db_session.query(SongRequestRow.status).filter_by(track_id=song.id)
    assert status.all() == [("accepted",)]  # in line, still shown in the queue


def test_a_request_in_line_is_not_picked_twice_and_is_played_when_it_starts(
    db_session: Session,
):
    user = make_user(db_session)
    song = make_track(db_session)
    service.create_request(db_session, user.id, "x", song.id)
    source = source_for(db_session)

    first = asyncio.run(source.next_track(user_id="g", recent_track_ids=[]))
    second = asyncio.run(source.next_track(user_id="g", recent_track_ids=[]))
    asyncio.run(source.track_started(song.id))

    assert first.track_id == song.id
    assert second.request is None  # not the same request again
    status = db_session.query(SongRequestRow.status).filter_by(track_id=song.id)
    assert status.all() == [("played",)]


def test_message_without_permission_is_not_passed_on(db_session: Session):
    user = make_user(db_session)
    song = make_track(db_session)
    service.create_request(db_session, user.id, "x", song.id, message="private words")

    info = asyncio.run(source_for(db_session).next_track(user_id="guest", recent_track_ids=[]))

    assert info.track_id == song.id
    assert info.request.messages == []


def test_without_requests_the_mood_target_chooses(db_session: Session):
    set_target("party")

    info = asyncio.run(source_for(db_session).next_track(user_id="g", recent_track_ids=[]))

    picked = db_session.get(TrackRow, info.track_id)
    assert picked.arousal >= 0.7  # a high-energy song from the real catalog or the test rows
    assert info.reason == "High energy to lift the room"
