from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.users.models import AuthSessionRow, ConsentRow, UserProfileRow, UserRow
from app.users.options import GENRES, LANGUAGES, NEWS_TOPICS
from app.users.privacy import CONSENT_KINDS, NOTICE_VERSION, PREFERENCE_LEARNING
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


def register(
    db: Session, username: str, password: str, preference_learning: bool = False
) -> UserRow:
    """Create an account with an empty profile and the consent chosen on the sign-up form.

    `username` must already be validated."""
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
    # Recorded even when declined: it shows the choice was offered and when.
    record_consent(db, user.id, PREFERENCE_LEARNING, preference_learning)
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


# ------------------------------------------------------------------ consents


def record_consent(db: Session, user_id: str, kind: str, granted: bool) -> ConsentRow:
    if kind not in CONSENT_KINDS:
        raise ValueError(f"unknown consent kind: {kind}")
    row = ConsentRow(user_id=user_id, kind=kind, granted=granted, notice_version=NOTICE_VERSION)
    db.add(row)
    db.flush()
    return row


def current_consents(db: Session, user_id: str) -> dict[str, ConsentRow | None]:
    """The latest decision per consent kind (None if never asked)."""
    rows = db.scalars(
        select(ConsentRow)
        .where(ConsentRow.user_id == user_id)
        .order_by(ConsentRow.created_at, ConsentRow.id)
    )
    latest: dict[str, ConsentRow | None] = dict.fromkeys(CONSENT_KINDS)
    for row in rows:
        latest[row.kind] = row
    return latest


def may_learn_preferences(db: Session, user_id: str) -> bool:
    """Whether listening behaviour may shape this user's music (#23 must check this)."""
    row = current_consents(db, user_id)[PREFERENCE_LEARNING]
    return bool(row and row.granted)


# ------------------------------------------------------- the listener's data


def export_user_data(db: Session, user: UserRow) -> dict:
    """Everything stored about the user, for 'download my data'. Secrets are left out:
    the password hash and the session tokens' hashes would only help an attacker."""
    sessions = db.scalars(
        select(AuthSessionRow)
        .where(AuthSessionRow.user_id == user.id)
        .order_by(AuthSessionRow.created_at)
    )
    consents = db.scalars(
        select(ConsentRow)
        .where(ConsentRow.user_id == user.id)
        .order_by(ConsentRow.created_at, ConsentRow.id)
    )
    return {
        "exported_at": _now().isoformat(),
        "account": {
            "id": user.id,
            "username": user.username,
            "created_at": user.created_at.isoformat(),
        },
        "profile": profile_from_row(get_profile_row(db, user.id)).model_dump(),
        "consents": [
            {
                "kind": c.kind,
                "granted": c.granted,
                "notice_version": c.notice_version,
                "at": c.created_at.isoformat(),
            }
            for c in consents
        ],
        "sign_ins": [
            {"created_at": s.created_at.isoformat(), "expires_at": s.expires_at.isoformat()}
            for s in sessions
        ],
    }


def delete_account(db: Session, user_id: str) -> None:
    """Delete the account; ON DELETE CASCADE removes every row that references it."""
    db.execute(delete(UserRow).where(UserRow.id == user_id))
    db.flush()
    db.expunge_all()  # loaded rows of this user are gone from the database
