from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.contracts import Track
from app.core.config import get_settings
from app.db.session import get_db
from app.music import TrackRow, track_from_row

router = APIRouter(prefix="/tracks")


def fold(value):
    """Lower-case, accent-free form of a column or text, for search (needs `unaccent`)."""
    return func.lower(func.unaccent(value))


def music_dir_dependency() -> Path:
    return get_settings().music_dir


@router.get("")
def list_tracks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    mood: str | None = None,
    q: str | None = Query(None, max_length=200),
    db: Session = Depends(get_db),
) -> list[Track]:
    query = select(TrackRow)
    if mood:
        query = query.where(TrackRow.mood_tags.contains([mood]))
    if q and q.strip():
        query = search_tracks(query, q.strip())
    else:
        query = query.order_by(TrackRow.created_at, TrackRow.id)
    rows = db.scalars(query.limit(limit).offset(offset))
    return [track_from_row(row) for row in rows]


def search_tracks(query, text: str):
    """Keep tracks whose title or artist contains `text`, ignoring case and accents.

    Best match first: the whole title/artist equals the text, then starts with it, then contains it.
    """
    needle = text.lower()
    # Escape LIKE wildcards in the user's text, then fold it in SQL like the columns.
    escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    title, artist = fold(TrackRow.title), fold(TrackRow.artist)
    exact, prefix, infix = fold(needle), fold(escaped + "%"), fold("%" + escaped + "%")
    rank = case(
        (or_(title == exact, artist == exact), 0),
        (or_(title.like(prefix), artist.like(prefix)), 1),
        else_=2,
    )
    return query.where(or_(title.like(infix), artist.like(infix))).order_by(
        rank, TrackRow.title, TrackRow.id
    )


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
