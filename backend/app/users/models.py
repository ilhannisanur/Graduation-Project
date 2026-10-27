import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_user_id() -> str:
    return f"usr_{uuid.uuid4().hex[:12]}"


def _text_list() -> Mapped[list[str]]:
    return mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"), default=list)


class UserRow(Base):
    """A listener account. Every table holding a user's data references users.id with
    ON DELETE CASCADE, so deleting this row deletes all of that user's data."""

    __tablename__ = "users"
    __table_args__ = (
        # Stored lowercased, so the unique index is also case-insensitive.
        CheckConstraint("username = lower(username)", name="ck_users_username_lowercase"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_user_id)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthSessionRow(Base):
    """A login session (the cookie). Not the broadcast session of the planner."""

    __tablename__ = "auth_sessions"

    # Only the hash is stored: a leaked database does not give working cookies.
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserProfileRow(Base):
    """Listening preferences. Values come from app.users.options (artists and city are free)."""

    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    genres: Mapped[list[str]] = _text_list()
    artists: Mapped[list[str]] = _text_list()
    languages: Mapped[list[str]] = _text_list()
    news_topics: Mapped[list[str]] = _text_list()
    weather_city: Mapped[str | None] = mapped_column(Text, default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
