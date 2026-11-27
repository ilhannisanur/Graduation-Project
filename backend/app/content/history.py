"""What the DJ said before (#74): the announcement log in the database."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.models import AnnouncementRow
from app.contracts import AnnouncementSpec

RECENT_LIMIT = 5


def load_recent_announcements(db: Session, limit: int = RECENT_LIMIT) -> list[str]:
    """The texts of the latest announcements, oldest first (the newest is last)."""
    rows = db.scalars(
        select(AnnouncementRow).order_by(AnnouncementRow.created_at.desc()).limit(limit)
    ).all()
    return [row.text for row in reversed(rows)]


def save_announcement(
    db: Session,
    spec: AnnouncementSpec,
    next_track_id: str | None,
    used_fallback: bool,
    opening_style: str | None = None,
) -> None:
    """Add one announcement to the log."""
    db.add(
        AnnouncementRow(
            kind=spec.kind.value,
            text=spec.text,
            emotion=spec.emotion.value,
            opening_style=opening_style,
            used_fallback=used_fallback,
            next_track_id=next_track_id,
        )
    )
    db.commit()
