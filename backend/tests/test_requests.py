import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts import RequestIntent
from app.db.session import get_db
from app.main import app
from app.music import TrackRow
from app.music.requests import SongRequestRow, service
from app.users import UserRow

PASSWORD = "correct horse battery"


@pytest.fixture
def client(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_track(db: Session, n: int, duration: float = 100.0) -> TrackRow:
    track = TrackRow(
        id=f"trk_req_{uuid.uuid4().hex[:8]}_{n}",
        title=f"Song {n}",
        artist="Some Artist",
        duration_seconds=duration,
        license="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        source_url=f"https://example.org/{n}",
        source="test-requests",
        source_track_id=f"{uuid.uuid4().hex[:8]}{n}",
    )
    db.add(track)
    db.flush()
    return track


def make_user(db: Session) -> UserRow:
    user = UserRow(username=f"test_{uuid.uuid4().hex[:12]}", password_hash="x")
    db.add(user)
    db.flush()
    return user


def login(client: TestClient) -> str:
    """Register a user through the API; the client keeps the login cookie."""
    name = f"test_{uuid.uuid4().hex[:12]}"
    response = client.post("/api/auth/register", json={"username": name, "password": PASSWORD})
    assert response.status_code == 201
    return response.json()["id"]


# ------------------------------------------------------------------------------- API


def test_requests_need_a_login(client: TestClient):
    assert client.post("/api/requests", json={"raw_text": "hi"}).status_code == 401
    assert client.get("/api/requests/mine").status_code == 401


def test_request_with_a_track_is_accepted_with_an_estimated_time(
    client: TestClient, db_session: Session
):
    user_id = login(client)
    track = make_track(db_session, 1)

    response = client.post(
        "/api/requests", json={"raw_text": "  Play Song 1 please ", "track_id": track.id}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == user_id
    assert body["raw_text"] == "Play Song 1 please"
    assert (body["status"], body["track_id"]) == ("accepted", track.id)
    assert body["estimated_play_time"] is not None
    assert "session_id" not in body


def test_request_without_a_track_waits_for_understanding(client: TestClient):
    login(client)

    body = client.post("/api/requests", json={"raw_text": "something calm"}).json()

    assert body["status"] == "received"
    assert body["track_id"] is None
    assert body["estimated_play_time"] is None


def test_bad_requests_are_refused(client: TestClient, db_session: Session):
    login(client)

    assert client.post("/api/requests", json={"raw_text": "   "}).status_code == 422
    assert client.post("/api/requests", json={"raw_text": "x" * 301}).status_code == 422
    unknown = client.post("/api/requests", json={"raw_text": "hi", "track_id": "trk_nope"})
    assert unknown.status_code == 404


def test_mine_lists_only_my_requests_newest_first(client: TestClient, db_session: Session):
    login(client)
    first = client.post("/api/requests", json={"raw_text": "first"}).json()
    second = client.post("/api/requests", json={"raw_text": "second"}).json()
    other = make_user(db_session)
    db_session.add(SongRequestRow(user_id=other.id, raw_text="not mine"))
    db_session.flush()

    mine = client.get("/api/requests/mine").json()

    assert [r["id"] for r in mine] == [second["id"], first["id"]]


def test_limit_of_waiting_requests_per_user(client: TestClient, db_session: Session):
    login(client)
    for n in range(service.MAX_PENDING_PER_USER):
        assert client.post("/api/requests", json={"raw_text": f"song {n}"}).status_code == 201

    response = client.post("/api/requests", json={"raw_text": "one too many"})

    assert response.status_code == 429


def test_played_requests_do_not_count_against_the_limit(client: TestClient, db_session: Session):
    user_id = login(client)
    track = make_track(db_session, 1)
    for n in range(service.MAX_PENDING_PER_USER):
        db_session.add(SongRequestRow(user_id=user_id, raw_text=f"old {n}", status="played"))
    db_session.flush()

    assert client.post("/api/requests", json={"raw_text": "new", "track_id": track.id}).status_code


def test_same_user_asking_for_the_same_song_gets_the_existing_request(
    client: TestClient, db_session: Session
):
    login(client)
    track = make_track(db_session, 1)
    first = client.post("/api/requests", json={"raw_text": "a", "track_id": track.id})

    again = client.post("/api/requests", json={"raw_text": "b", "track_id": track.id})

    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["id"] == first.json()["id"]
    assert len(client.get("/api/requests/mine").json()) == 1


# ---------------------------------------------------------------------------- queue


def test_same_track_from_several_users_is_merged(db_session: Session):
    a, b, c = (make_user(db_session) for _ in range(3))
    popular, other = make_track(db_session, 1), make_track(db_session, 2)
    ra, _ = service.create_request(db_session, a.id, "x", popular.id)
    rb, _ = service.create_request(db_session, b.id, "y", other.id)
    rc, _ = service.create_request(db_session, c.id, "z", popular.id)

    group = service.next_group(db_session)

    assert [r.id for r in group] == [ra.id, rc.id]  # one slot for the popular track
    times = service.estimated_play_times(db_session)
    assert times[ra.id] == times[rc.id]
    assert times[rb.id] > times[ra.id]


def test_queue_order_follows_the_first_request_of_each_track(db_session: Session):
    user = make_user(db_session)
    first, second = make_track(db_session, 1), make_track(db_session, 2)
    r1, _ = service.create_request(db_session, user.id, "1", first.id)
    r2, _ = service.create_request(db_session, user.id, "2", second.id)

    assert [r.id for r in service.next_group(db_session)] == [r1.id]
    service.mark_played(db_session, first.id)
    assert [r.id for r in service.next_group(db_session)] == [r2.id]
    service.mark_played(db_session, second.id)
    assert service.next_group(db_session) == []


def test_estimated_time_adds_the_tracks_ahead(db_session: Session):
    user = make_user(db_session)
    first, second = make_track(db_session, 1, 120.0), make_track(db_session, 2, 60.0)
    r1, _ = service.create_request(db_session, user.id, "1", first.id)
    r2, _ = service.create_request(db_session, user.id, "2", second.id)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    times = service.estimated_play_times(db_session, now)

    assert times[r1.id] == now
    assert times[r2.id] == now + timedelta(seconds=120.0 + service.SLOT_OVERHEAD_SECONDS)


def test_mark_played_finishes_all_requests_for_the_track(db_session: Session):
    a, b = make_user(db_session), make_user(db_session)
    track = make_track(db_session, 1)
    service.create_request(db_session, a.id, "x", track.id)
    service.create_request(db_session, b.id, "y", track.id)

    assert service.mark_played(db_session, track.id) == 2

    statuses = db_session.scalars(
        select(SongRequestRow.status).where(SongRequestRow.track_id == track.id)
    ).all()
    assert statuses == ["played", "played"]


def test_accept_and_reject_by_dj_brain(db_session: Session):
    user = make_user(db_session)
    track = make_track(db_session, 1)
    waiting, _ = service.create_request(db_session, user.id, "play song one")
    refused, _ = service.create_request(db_session, user.id, "play something rude")

    service.accept(db_session, waiting.id, track.id, RequestIntent(song_title="Song 1"))
    service.reject(db_session, refused.id, "not allowed")

    assert (waiting.status, waiting.track_id) == ("accepted", track.id)
    assert waiting.intent["song_title"] == "Song 1"
    assert (refused.status, refused.reject_reason) == ("rejected", "not allowed")
    assert [r.id for r in service.next_group(db_session)] == [waiting.id]


# ------------------------------------------------------------------ message consent


def test_message_is_read_on_air_only_with_permission(db_session: Session):
    user = make_user(db_session)
    intent = RequestIntent(song_title="Song 1", message="For my sister's birthday")
    allowed, _ = service.create_request(db_session, user.id, "a", message_readout_allowed=True)
    not_allowed, _ = service.create_request(db_session, user.id, "b")
    allowed.intent = not_allowed.intent = intent.model_dump()

    assert service.shoutout_message(allowed) == "For my sister's birthday"
    assert service.shoutout_message(not_allowed) is None


def test_no_message_means_nothing_to_read(db_session: Session):
    user = make_user(db_session)
    row, _ = service.create_request(db_session, user.id, "a", message_readout_allowed=True)
    row.intent = RequestIntent(song_title="Song 1").model_dump()

    assert service.shoutout_message(row) is None


# ------------------------------------------------------------------------- privacy


def test_requests_are_in_the_data_export_and_deleted_with_the_account(
    client: TestClient, db_session: Session
):
    user_id = login(client)
    client.post("/api/requests", json={"raw_text": "my private wish"})

    export = client.get("/api/me/data")

    assert export.status_code == 200
    assert [r["text"] for r in export.json()["song_requests"]] == ["my private wish"]

    deleted = client.request("DELETE", "/api/me", json={"password": PASSWORD})
    assert deleted.status_code in (200, 204)
    left = db_session.scalars(select(SongRequestRow).where(SongRequestRow.user_id == user_id))
    assert left.all() == []
