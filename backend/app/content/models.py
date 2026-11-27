import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_announcement_id() -> str:
    return f"ann_{uuid.uuid4().hex[:12]}"


class AnnouncementRow(Base):
    """Something the DJ said on air (#74). DJ Brain reads the latest ones so it does not
    repeat itself, and the log is our data for measuring the announcements.

    Request shout-outs are not stored: they contain the listener's name and message.
    """

    __tablename__ = "announcements"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_announcement_id)
    kind: Mapped[str] = mapped_column(String)  # AnnouncementKind, e.g. "song_intro"
    text: Mapped[str] = mapped_column(Text)
    emotion: Mapped[str] = mapped_column(String)
    # The opening style Python chose for the LLM; None when no style was given.
    opening_style: Mapped[str | None] = mapped_column(String, default=None)
    # True when the LLM did not answer and a template was used.
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    # The song the announcement introduces. Kept as NULL if the song leaves the catalog.
    next_track_id: Mapped[str | None] = mapped_column(
        ForeignKey("tracks.id", ondelete="SET NULL"), default=None
    )
    # Set in Python too, so announcements saved in one transaction keep their order.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        index=True,
    )
