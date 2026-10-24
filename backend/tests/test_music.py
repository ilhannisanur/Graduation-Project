import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.contracts import Track
from app.core.config import get_settings
from app.music import TrackRow, track_from_row


def make_row(**overrides) -> TrackRow:
    values = {
        "id": "trk_001",
        "title": "Morning Rain",
        "artist": "Some Artist",
        "duration_seconds": 184.5,
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "source_url": "https://example.org/tracks/morning-rain",
        "mood_tags": ["calm", "acoustic"],
        "valence": 0.62,
        "arousal": 0.25,
        "file_path": "audio/48/948.mp3",
        "source": "jamendo",
        "source_track_id": "948",
    }
    return TrackRow(**{**values, **overrides})


def test_row_converts_to_track_without_file_path():
    track = track_from_row(make_row())

    assert isinstance(track, Track)
    assert track.id == "trk_001"
    assert track.mood_tags == ["calm", "acoustic"]
    dumped = track.model_dump()
    assert "file_path" not in dumped
    assert "source" not in dumped
    assert "source_track_id" not in dumped
    assert "audio/48/948.mp3" not in track.model_dump_json()


def test_row_with_no_analysis_gives_null_valence_arousal():
    track = track_from_row(make_row(valence=None, arousal=None, mood_tags=None))

    assert track.valence is None
    assert track.arousal is None
    assert track.mood_tags == []


def test_source_and_source_track_id_are_unique_in_schema():
    constraints = TrackRow.__table__.constraints
    unique_columns = [
        {c.name for c in constraint.columns}
        for constraint in constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    ]
    assert {"source", "source_track_id"} in unique_columns


@pytest.fixture
def db_session():
    # Needs the Docker Postgres with migrations applied (alembic upgrade head).
    # CI has no Postgres service, so this is skipped there.
    engine = create_engine(get_settings().database_url, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM tracks LIMIT 1"))
    except (OperationalError, ProgrammingError):
        # OperationalError: Postgres is down; ProgrammingError: migrations not applied.
        pytest.skip("Postgres with the tracks table is not available")
    with engine.connect() as conn:
        transaction = conn.begin()
        session = Session(bind=conn, join_transaction_mode="create_savepoint")
        yield session
        session.close()
        transaction.rollback()


def test_same_source_track_cannot_be_inserted_twice(db_session: Session):
    db_session.add(make_row(id="trk_dup_a", source_track_id="dup-1"))
    db_session.flush()
    db_session.add(make_row(id="trk_dup_b", source_track_id="dup-1"))

    with pytest.raises(IntegrityError):
        db_session.flush()
