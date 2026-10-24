import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_track_id() -> str:
    return f"trk_{uuid.uuid4().hex[:12]}"


class TrackRow(Base):
    """A catalog track. Public fields mirror app.contracts.Track; the rest are internal."""

    __tablename__ = "tracks"
    __table_args__ = (
        UniqueConstraint("source", "source_track_id", name="uq_tracks_source_source_track_id"),
        CheckConstraint("duration_seconds > 0", name="ck_tracks_duration_positive"),
        CheckConstraint(
            "valence IS NULL OR (valence >= 0 AND valence <= 1)", name="ck_tracks_valence_range"
        ),
        CheckConstraint(
            "arousal IS NULL OR (arousal >= 0 AND arousal <= 1)", name="ck_tracks_arousal_range"
        ),
    )

    # Contract fields
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_track_id)
    title: Mapped[str] = mapped_column(Text)
    artist: Mapped[str] = mapped_column(Text)
    duration_seconds: Mapped[float] = mapped_column(Float)
    license: Mapped[str] = mapped_column(String)
    license_url: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    # Flat list of strings: ARRAY supports @> / && lookups without extra tables.
    mood_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]"), default=list
    )
    valence: Mapped[float | None] = mapped_column(Float, default=None)
    arousal: Mapped[float | None] = mapped_column(Float, default=None)

    # Internal fields (never leave the database layer)
    file_path: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[str] = mapped_column(String)  # e.g. "jamendo"
    source_track_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
