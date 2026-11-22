import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app
from app.music import TrackRow

# A tag no real catalog track has, so the tests ignore whatever is already in the database.
TAG = "zz-search-mood"


@pytest.fixture
def client(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def add_track(db: Session, n: int, title: str, artist: str, tags: list[str] | None = None) -> None:
    db.add(
        TrackRow(
            id=f"trk_search_{n}",
            title=title,
            artist=artist,
            duration_seconds=100.0,
            license="CC BY 4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            source_url=f"https://example.org/{n}",
            mood_tags=tags if tags is not None else [TAG],
            source="test-search",
            source_track_id=str(n),
        )
    )


def search(client: TestClient, q: str, **params) -> list[str]:
    response = client.get("/api/tracks", params={"q": q, "mood": TAG, "limit": 100, **params})
    assert response.status_code == 200
    return [t["title"] for t in response.json()]


def test_matches_title_and_artist_ignoring_case(client: TestClient, db_session: Session):
    add_track(db_session, 1, "Midnight Rain", "Zzqx Band")
    add_track(db_session, 2, "Other", "Someone")
    db_session.flush()

    assert search(client, "MIDNIGHT") == ["Midnight Rain"]
    assert search(client, "zzqx band") == ["Midnight Rain"]
    assert search(client, "rain") == ["Midnight Rain"]


def test_turkish_and_accented_names(client: TestClient, db_session: Session):
    add_track(db_session, 1, "Şarkı Zzqx", "Ömer Çağlar")
    add_track(db_session, 2, "ISPARTA Zzqx", "İpek Işık")
    add_track(db_session, 3, "Café Zzqx", "Beyoncé")
    db_session.flush()

    assert search(client, "sarki zzqx") == ["Şarkı Zzqx"]
    assert search(client, "ŞARKI") == ["Şarkı Zzqx"]
    assert search(client, "omer caglar") == ["Şarkı Zzqx"]
    assert search(client, "ipek isik") == ["ISPARTA Zzqx"]
    assert search(client, "isparta") == ["ISPARTA Zzqx"]
    assert search(client, "cafe") == ["Café Zzqx"]
    assert search(client, "beyonce") == ["Café Zzqx"]
    assert search(client, "café") == ["Café Zzqx"]


def test_best_match_comes_first(client: TestClient, db_session: Session):
    add_track(db_session, 1, "The Zzqx Song", "A")  # contains
    add_track(db_session, 2, "Zzqx Song Two", "B")  # starts with
    add_track(db_session, 3, "Zzqx", "C")  # exact
    db_session.flush()

    assert search(client, "zzqx") == ["Zzqx", "Zzqx Song Two", "The Zzqx Song"]


def test_no_match_gives_empty_list(client: TestClient, db_session: Session):
    add_track(db_session, 1, "Something", "Someone")
    db_session.flush()

    assert search(client, "nothing-like-this") == []


def test_q_works_with_mood_limit_and_offset(client: TestClient, db_session: Session):
    add_track(db_session, 1, "Zzqx A", "X")
    add_track(db_session, 2, "Zzqx B", "X")
    add_track(db_session, 3, "Zzqx C", "X")
    add_track(db_session, 4, "Zzqx Other Mood", "X", tags=["different"])
    db_session.flush()

    assert search(client, "zzqx") == ["Zzqx A", "Zzqx B", "Zzqx C"]
    assert search(client, "zzqx", limit=2) == ["Zzqx A", "Zzqx B"]
    assert search(client, "zzqx", limit=2, offset=2) == ["Zzqx C"]


def test_wildcards_are_taken_literally(client: TestClient, db_session: Session):
    add_track(db_session, 1, "100% Zzqx", "X")
    add_track(db_session, 2, "Plain Zzqx", "X")
    db_session.flush()

    assert search(client, "%") == ["100% Zzqx"]
    assert search(client, "_") == []


def test_blank_q_is_ignored(client: TestClient, db_session: Session):
    add_track(db_session, 1, "Zzqx A", "X")
    db_session.flush()

    assert search(client, "   ") == ["Zzqx A"]
