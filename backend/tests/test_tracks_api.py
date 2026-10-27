import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


def add_track(db: Session, n: int, tags: list[str]) -> None:
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
            file_path=f"audio/secret-{n}.mp3",
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
    add_track(db_session, 1, [TAG])
    db_session.flush()

    listing = client.get("/api/tracks", params={"mood": TAG})
    single = client.get("/api/tracks/trk_test_1")

    assert single.status_code == 200
    assert single.json()["title"] == "Song 1"
    assert "file_path" not in single.json()
    assert "secret-1" not in listing.text + single.text


def test_unknown_track_is_404(client: TestClient):
    assert client.get("/api/tracks/trk_nope").status_code == 404


def test_limit_is_validated(client: TestClient):
    assert client.get("/api/tracks", params={"limit": 0}).status_code == 422
    assert client.get("/api/tracks", params={"limit": 1000}).status_code == 422
