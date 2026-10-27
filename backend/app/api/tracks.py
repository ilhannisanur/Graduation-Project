from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts import Track
from app.core.config import get_settings
from app.db.session import get_db
from app.music import TrackRow, track_from_row

router = APIRouter(prefix="/tracks")


def music_dir_dependency() -> Path:
    return get_settings().music_dir


@router.get("")
def list_tracks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    mood: str | None = None,
    db: Session = Depends(get_db),
) -> list[Track]:
    query = select(TrackRow).order_by(TrackRow.created_at, TrackRow.id)
    if mood:
        query = query.where(TrackRow.mood_tags.contains([mood]))
    rows = db.scalars(query.limit(limit).offset(offset))
    return [track_from_row(row) for row in rows]


@router.get("/{track_id}")
def get_track(track_id: str, db: Session = Depends(get_db)) -> Track:
    row = db.get(TrackRow, track_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Track not found")
    return track_from_row(row)


@router.get("/{track_id}/audio")
def get_track_audio(
    track_id: str,
    db: Session = Depends(get_db),
    music_dir: Path = Depends(music_dir_dependency),
) -> FileResponse:
    """The audio file of a track. Range requests are supported (seeking, mobile browsers)."""
    row = db.get(TrackRow, track_id)
    if row is None or not row.file_path:
        raise HTTPException(status_code=404, detail="Track not found")
    root = music_dir.resolve()
    path = (root / row.file_path).resolve()
    # The path comes from the database, but never serve anything outside the music folder.
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(path, media_type="audio/mpeg")
