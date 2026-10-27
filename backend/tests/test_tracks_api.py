from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.tracks import music_dir_dependency
from app.db.session import get_db
from app.main import app
from app.music import TrackRow

# A tag no real catalog track has, so the tests ignore whatever is already in the database.
TAG = "zz-test-mood"


@pytest.fixture
def client(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def add_track(db: Session, n: int, tags: list[str], file_path: str | None = None) -> None:
    db.add(
        TrackRow(
            id=f"trk_test_{n}",
            title=f"Song {n}",
            artist="Some Artist",
            duration_seconds=100.0,
            license="CC BY 4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            source_url=f"https://example.org/{n}",
            mood_tags=tags,
            file_path=file_path,
            source="test-api",
            source_track_id=str(n),
        )
    )


def test_list_filters_by_mood_and_pages(client: TestClient, db_session: Session):
    for n in range(3):
        add_track(db_session, n, [TAG, "calm"])
    add_track(db_session, 9, ["other"])
    db_session.flush()

    everything = client.get("/api/tracks", params={"mood": TAG, "limit": 100}).json()
    first_page = client.get("/api/tracks", params={"mood": TAG, "limit": 2}).json()
    second_page = client.get("/api/tracks", params={"mood": TAG, "limit": 2, "offset": 2}).json()

    assert sorted(t["id"] for t in everything) == ["trk_test_0", "trk_test_1", "trk_test_2"]
    assert len(first_page) == 2
    assert len(second_page) == 1
    assert {t["id"] for t in first_page + second_page} == {t["id"] for t in everything}


def test_file_path_is_not_in_the_response(client: TestClient, db_session: Session):
    add_track(db_session, 1, [TAG], file_path="audio/secret-1.mp3")
    db_session.flush()

    listing = client.get("/api/tracks", params={"mood": TAG})
    single = client.get("/api/tracks/trk_test_1")

    assert single.status_code == 200
    assert single.json()["title"] == "Song 1"
    assert "file_path" not in single.json()
    assert "secret-1" not in listing.text + single.text


AUDIO = bytes(range(100))


@pytest.fixture
def music_dir(tmp_path: Path):
    (tmp_path / "audio").mkdir()
    (tmp_path / "audio" / "1.mp3").write_bytes(AUDIO)
    app.dependency_overrides[music_dir_dependency] = lambda: tmp_path
    return tmp_path


def test_audio_is_served(client: TestClient, db_session: Session, music_dir: Path):
    add_track(db_session, 1, [TAG], file_path="audio/1.mp3")
    db_session.flush()

    response = client.get("/api/tracks/trk_test_1/audio")

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.content == AUDIO


def test_audio_supports_range_requests(client: TestClient, db_session: Session, music_dir: Path):
    add_track(db_session, 1, [TAG], file_path="audio/1.mp3")
    db_session.flush()

    response = client.get("/api/tracks/trk_test_1/audio", headers={"Range": "bytes=10-19"})

    assert response.status_code == 206
    assert response.content == AUDIO[10:20]
    assert response.headers["content-range"] == "bytes 10-19/100"


def test_audio_outside_music_folder_is_not_served(
    client: TestClient, db_session: Session, music_dir: Path
):
    secret = music_dir.parent / "secret.mp3"
    secret.write_bytes(b"secret")
    add_track(db_session, 1, [TAG], file_path="../secret.mp3")
    db_session.flush()

    response = client.get("/api/tracks/trk_test_1/audio")

    assert response.status_code == 404
    assert b"secret" not in response.content


def test_audio_404_for_unknown_track_missing_file_or_no_path(
    client: TestClient, db_session: Session, music_dir: Path
):
    add_track(db_session, 1, [TAG], file_path="audio/gone.mp3")
    add_track(db_session, 2, [TAG], file_path=None)
    db_session.flush()

    assert client.get("/api/tracks/trk_nope/audio").status_code == 404
    assert client.get("/api/tracks/trk_test_1/audio").status_code == 404
    assert client.get("/api/tracks/trk_test_2/audio").status_code == 404


def test_unknown_track_is_404(client: TestClient):
    assert client.get("/api/tracks/trk_nope").status_code == 404


def test_limit_is_validated(client: TestClient):
    assert client.get("/api/tracks", params={"limit": 0}).status_code == 422
    assert client.get("/api/tracks", params={"limit": 1000}).status_code == 422
