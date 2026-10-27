from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts import Track
from app.db.session import get_db
from app.music import TrackRow, track_from_row

router = APIRouter(prefix="/tracks")


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
