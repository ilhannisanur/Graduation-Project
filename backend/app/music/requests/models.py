import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


class SongRequestRow(Base):
    """A listener's song request in the shared queue. Fields mirror app.contracts.SongRequest;
    deleting the user deletes their requests (ON DELETE CASCADE, like all personal data)."""

    __tablename__ = "song_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('received', 'accepted', 'rejected', 'played')",
            name="ck_song_requests_status",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_request_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    # RequestIntent as JSON; filled by DJ Brain (#13).
    intent: Mapped[dict | None] = mapped_column(JSONB, default=None)
    # The catalog track the request resolved to. Requests for the same track are merged in the
    # queue: the track plays once and all of them become "played".
    track_id: Mapped[str | None] = mapped_column(
        ForeignKey("tracks.id", ondelete="SET NULL"), index=True, default=None
    )
    status: Mapped[str] = mapped_column(String, default="received")
    reject_reason: Mapped[str | None] = mapped_column(Text, default=None)
    # The listener's explicit permission to read their message on air. Asked per request.
    message_readout_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    # Set in Python (not only by the database) so requests made in one transaction keep their order.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
