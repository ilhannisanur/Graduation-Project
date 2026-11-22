"""The shared song-request queue.

One queue for all listeners, ordered by when each track was first requested. Requests for the
same track are merged: the track plays once and every request for it becomes "played".
The planner (#14) takes the next group with `next_group` and reports with `mark_played`;
DJ Brain (#13) calls `accept` / `reject` once it has understood the text.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.contracts import RequestIntent, RequestStatus, SongRequest
from app.music.models import TrackRow
from app.music.requests.models import SongRequestRow

# A listener can have this many requests waiting (received or accepted) at the same time.
MAX_PENDING_PER_USER = 3
# Rough extra time per queued track: the DJ intro and the request shout-out.
SLOT_OVERHEAD_SECONDS = 30.0
# Used when a track has no usable duration.
FALLBACK_TRACK_SECONDS = 210.0

PENDING = (RequestStatus.RECEIVED.value, RequestStatus.ACCEPTED.value)


class TooManyPending(Exception):
    pass


class UnknownTrack(Exception):
    pass


class UnknownRequest(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def create_request(
    db: Session,
    user_id: str,
    raw_text: str,
    track_id: str | None = None,
    message_readout_allowed: bool = False,
) -> tuple[SongRequestRow, bool]:
    """Add a request. Returns (request, created); created is False when the user already has a
    pending request for the same track (the existing one is returned, nothing is added).

    With a track_id the request is accepted at once; without one it stays "received" until
    DJ Brain has understood the text. The caller commits.
    """
    if track_id is not None and db.get(TrackRow, track_id) is None:
        raise UnknownTrack(track_id)

    pending = list(
        db.scalars(
            select(SongRequestRow).where(
                SongRequestRow.user_id == user_id, SongRequestRow.status.in_(PENDING)
            )
        )
    )
    if track_id is not None:
        for existing in pending:
            if existing.track_id == track_id:
                return existing, False
    if len(pending) >= MAX_PENDING_PER_USER:
        raise TooManyPending(user_id)

    row = SongRequestRow(
        user_id=user_id,
        raw_text=raw_text,
        track_id=track_id,
        status=(RequestStatus.ACCEPTED if track_id else RequestStatus.RECEIVED).value,
        message_readout_allowed=message_readout_allowed,
    )
    db.add(row)
    db.flush()
    return row, True


def accept(
    db: Session, request_id: str, track_id: str, intent: RequestIntent | None = None
) -> SongRequestRow:
    """DJ Brain understood the request and Music found the track. The caller commits."""
    row = _get(db, request_id)
    if db.get(TrackRow, track_id) is None:
        raise UnknownTrack(track_id)
    row.status = RequestStatus.ACCEPTED.value
    row.track_id = track_id
    row.reject_reason = None
    if intent is not None:
        row.intent = intent.model_dump()
    db.flush()
    return row


def reject(db: Session, request_id: str, reason: str) -> SongRequestRow:
    """The request cannot be played (not understood, not in the catalog, filtered)."""
    row = _get(db, request_id)
    row.status = RequestStatus.REJECTED.value
    row.reject_reason = reason
    db.flush()
    return row


def _get(db: Session, request_id: str) -> SongRequestRow:
    row = db.get(SongRequestRow, request_id)
    if row is None:
        raise UnknownRequest(request_id)
    return row


def _accepted(db: Session) -> list[SongRequestRow]:
    return list(
        db.scalars(
            select(SongRequestRow)
            .where(
                SongRequestRow.status == RequestStatus.ACCEPTED.value,
                SongRequestRow.track_id.is_not(None),
            )
            .order_by(SongRequestRow.created_at, SongRequestRow.id)
        )
    )


def _groups(rows: list[SongRequestRow]) -> list[list[SongRequestRow]]:
    """Merge requests for the same track; groups keep the order of their first request."""
    groups: dict[str, list[SongRequestRow]] = {}
    for row in rows:
        groups.setdefault(row.track_id, []).append(row)
    return list(groups.values())


def next_group(db: Session) -> list[SongRequestRow]:
    """All accepted requests for the track that should play next ([] if the queue is empty)."""
    groups = _groups(_accepted(db))
    return groups[0] if groups else []


def mark_played(db: Session, track_id: str, now: datetime | None = None) -> int:
    """The track was played: every accepted request for it is done. Returns how many."""
    result = db.execute(
        update(SongRequestRow)
        .where(
            SongRequestRow.track_id == track_id,
            SongRequestRow.status == RequestStatus.ACCEPTED.value,
        )
        .values(status=RequestStatus.PLAYED.value, played_at=now or _now())
    )
    return result.rowcount


def estimated_play_times(db: Session, now: datetime | None = None) -> dict[str, datetime]:
    """Rough play time per accepted request id: now plus the tracks queued ahead of it.

    Merged requests share one time. It is an estimate: the song playing right now and
    the planner's own choices are not known here.
    """
    start = now or _now()
    groups = _groups(_accepted(db))
    durations = dict(
        db.execute(
            select(TrackRow.id, TrackRow.duration_seconds).where(
                TrackRow.id.in_([g[0].track_id for g in groups])
            )
        ).all()
    )
    times: dict[str, datetime] = {}
    offset = 0.0
    for group in groups:
        when = start + timedelta(seconds=offset)
        for row in group:
            times[row.id] = when
        track_seconds = durations.get(group[0].track_id) or FALLBACK_TRACK_SECONDS
        offset += track_seconds + SLOT_OVERHEAD_SECONDS
    return times


def requests_of_user(db: Session, user_id: str, limit: int = 50) -> list[SongRequestRow]:
    return list(
        db.scalars(
            select(SongRequestRow)
            .where(SongRequestRow.user_id == user_id)
            .order_by(SongRequestRow.created_at.desc(), SongRequestRow.id)
            .limit(limit)
        )
    )


def pending_count(db: Session, user_id: str) -> int:
    return db.scalar(
        select(func.count())
        .select_from(SongRequestRow)
        .where(SongRequestRow.user_id == user_id, SongRequestRow.status.in_(PENDING))
    )


def shoutout_message(row: SongRequestRow) -> str | None:
    """The listener's message for the on-air shout-out. Only with their permission."""
    if not row.message_readout_allowed or not row.intent:
        return None
    return (row.intent.get("message") or "").strip() or None


def to_contract(row: SongRequestRow, estimated_play_time: datetime | None = None) -> SongRequest:
    return SongRequest(
        id=row.id,
        user_id=row.user_id,
        raw_text=row.raw_text,
        intent=RequestIntent.model_validate(row.intent) if row.intent else None,
        status=RequestStatus(row.status),
        reject_reason=row.reject_reason,
        track_id=row.track_id,
        estimated_play_time=estimated_play_time,
    )
