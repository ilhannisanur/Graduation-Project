from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.users.models import AuthSessionRow, UserProfileRow, UserRow
from app.users.options import GENRES, LANGUAGES, NEWS_TOPICS
from app.users.schemas import Profile, normalize_username
from app.users.security import (
    dummy_hash,
    hash_password,
    needs_rehash,
    new_session_token,
    token_hash,
    verify_password,
)

SESSION_DAYS = 30


class UsernameTaken(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def register(db: Session, username: str, password: str) -> UserRow:
    """Create an account with an empty profile. `username` must already be validated."""
    if db.scalar(select(UserRow.id).where(UserRow.username == username)):
        raise UsernameTaken(username)
    user = UserRow(username=username, password_hash=hash_password(password))
    try:
        # Two registrations at once: the unique index decides. The savepoint keeps the
        # rest of the transaction usable if this insert fails.
        with db.begin_nested():
            db.add(user)
    except IntegrityError:
        raise UsernameTaken(username) from None
    db.add(UserProfileRow(user_id=user.id))
    db.flush()
    return user


def authenticate(db: Session, username: str, password: str) -> UserRow | None:
    user = db.scalar(select(UserRow).where(UserRow.username == normalize_username(username)))
    if user is None:
        verify_password(dummy_hash(), password)  # same work as a real check
        return None
    if not verify_password(user.password_hash, password):
        return None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def start_session(db: Session, user: UserRow, now: datetime | None = None) -> str:
    """Create a login session and return its token (the cookie value). Only the hash is kept."""
    now = now or _now()
    db.execute(
        delete(AuthSessionRow).where(
            AuthSessionRow.user_id == user.id, AuthSessionRow.expires_at <= now
        )
    )
    token = new_session_token()
    db.add(
        AuthSessionRow(
            token_hash=token_hash(token),
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(days=SESSION_DAYS),
        )
    )
    db.flush()
    return token


def end_session(db: Session, token: str) -> None:
    db.execute(delete(AuthSessionRow).where(AuthSessionRow.token_hash == token_hash(token)))


def user_for_token(db: Session, token: str, now: datetime | None = None) -> UserRow | None:
    return db.scalar(
        select(UserRow)
        .join(AuthSessionRow, AuthSessionRow.user_id == UserRow.id)
        .where(
            AuthSessionRow.token_hash == token_hash(token),
            AuthSessionRow.expires_at > (now or _now()),
        )
    )


def get_profile_row(db: Session, user_id: str) -> UserProfileRow:
    row = db.get(UserProfileRow, user_id)
    if row is None:  # every account gets one at registration; this is only a safety net
        row = UserProfileRow(user_id=user_id)
        db.add(row)
        db.flush()
    return row


def profile_from_row(row: UserProfileRow) -> Profile:
    # Choices that were later removed from the options are dropped instead of failing.
    return Profile(
        genres=[g for g in row.genres if g in GENRES],
        artists=list(row.artists),
        languages=[lang for lang in row.languages if lang in LANGUAGES],
        news_topics=[t for t in row.news_topics if t in NEWS_TOPICS],
        weather_city=row.weather_city,
    )


def update_profile(db: Session, user_id: str, profile: Profile) -> UserProfileRow:
    row = get_profile_row(db, user_id)
    row.genres = profile.genres
    row.artists = profile.artists
    row.languages = profile.languages
    row.news_topics = profile.news_topics
    row.weather_city = profile.weather_city
    db.flush()
    return row
