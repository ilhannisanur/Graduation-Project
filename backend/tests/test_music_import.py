import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.music import TrackRow
from app.music.import_catalog import import_catalog


def entry(source_id: str, **overrides) -> dict:
    return {
        "source": "test-import",
        "source_track_id": source_id,
        "title": f"Song {source_id}",
        "artist": "Some Artist",
        "duration_seconds": 120.0,
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "source_url": f"https://example.org/track/{source_id}",
        "mood_tags": ["calm"],
        "file": f"{source_id}.mp3",
        **overrides,
    }


def make_catalog(music_dir: Path, entries: list[dict], with_audio: bool = True) -> None:
    (music_dir / "audio").mkdir(parents=True, exist_ok=True)
    manifest = {"version": 1, "source": "test-import", "tracks": entries}
    (music_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if with_audio:
        for e in entries:
            (music_dir / "audio" / e["file"]).write_bytes(b"audio")


def count(session: Session) -> int:
    return session.scalar(
        select(func.count()).select_from(TrackRow).where(TrackRow.source == "test-import")
    )


def test_import_adds_tracks(db_session: Session, tmp_path: Path):
    make_catalog(tmp_path, [entry("1"), entry("2")])

    summary = import_catalog(db_session, tmp_path, out=lambda _: None)

    assert (summary.added, summary.updated, summary.unchanged) == (2, 0, 0)
    assert count(db_session) == 2
    row = db_session.scalar(select(TrackRow).where(TrackRow.source_track_id == "1"))
    assert row.file_path == "audio/1.mp3"
    assert row.mood_tags == ["calm"]


def test_second_run_does_not_add_again(db_session: Session, tmp_path: Path):
    make_catalog(tmp_path, [entry("1"), entry("2")])
    import_catalog(db_session, tmp_path, out=lambda _: None)

    summary = import_catalog(db_session, tmp_path, out=lambda _: None)

    assert (summary.added, summary.updated, summary.unchanged) == (0, 0, 2)
    assert count(db_session) == 2


def test_changed_info_is_updated_and_analysis_is_kept(db_session: Session, tmp_path: Path):
    make_catalog(tmp_path, [entry("1")])
    import_catalog(db_session, tmp_path, out=lambda _: None)
    row = db_session.scalar(select(TrackRow).where(TrackRow.source_track_id == "1"))
    row.valence = 0.7
    db_session.flush()
    track_id = row.id

    make_catalog(tmp_path, [entry("1", title="New Title", mood_tags=["calm", "soft"])])
    summary = import_catalog(db_session, tmp_path, out=lambda _: None)

    assert (summary.added, summary.updated) == (0, 1)
    db_session.refresh(row)
    assert row.title == "New Title"
    assert row.mood_tags == ["calm", "soft"]
    assert row.valence == 0.7
    assert row.id == track_id


def test_track_without_audio_file_is_skipped(db_session: Session, tmp_path: Path):
    make_catalog(tmp_path, [entry("1"), entry("2")])
    (tmp_path / "audio" / "2.mp3").unlink()

    summary = import_catalog(db_session, tmp_path, out=lambda _: None)

    assert summary.added == 1
    assert summary.skipped == ["2"]
    assert count(db_session) == 1
