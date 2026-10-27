"""Broadcast planner: builds the song -> announcement -> song order per listener.

How it works
------------
Every session plans *blocks*. A block is one song, optionally preceded by an
announcement that introduces it::

    block 0: [song A]
    block 1: [announcement "...up next B"] [song B]
    block 2: [announcement "...up next C"] [song C]

As soon as a segment is handed out, the next block is prepared in the
background: the song is picked first (fast), then the director writes the
announcement and the Speech service voices it (slow). So by the time the
player asks for the next segment, it is normally ready.

No silence
----------
``next_segment`` never waits for speech. If the announcement is not ready (or
failed), the planner skips it and returns the song instead. If the music
source is down, it replays a recent song rather than stopping.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from uuid import uuid4

from .models import (
    AnnouncementRequest,
    NextSegmentResponse,
    QueuedAnnouncement,
    QueuedTrack,
    TrackInfo,
)
from .ports import AnnouncementDirector, MusicSource, SpeechSynthesizer

logger = logging.getLogger(__name__)


class PlannerError(Exception):
    pass


class SessionNotFound(PlannerError):
    pass


class NoTrackAvailable(PlannerError):
    pass


class TooManySessions(PlannerError):
    pass


@dataclass
class PlannerSettings:
    songs_per_announcement: int = 1  # songs between two announcements (requirement 12)
    music_timeout_s: float = 5.0  # longest wait for the music source
    # time budget for director + speech, spent in the background
    announcement_timeout_s: float = 90.0
    # how long /next may wait for an unfinished announcement (0 = never wait)
    announcement_wait_s: float = 0.0
    recent_tracks: int = 30  # history passed to the music source to avoid repeats
    session_ttl_s: float = 2 * 60 * 60  # idle sessions are closed after this
    max_sessions: int = 500
    track_audio_url: str = "/api/tracks/{track_id}/audio"  # served by #42

    def __post_init__(self) -> None:
        if self.songs_per_announcement < 1:
            raise ValueError("songs_per_announcement must be at least 1")


@dataclass
class _Block:
    index: int
    track: TrackInfo
    announcement: asyncio.Task[QueuedAnnouncement | None] | None


@dataclass(eq=False)
class Session:
    session_id: str
    user_id: str
    last_seen: float
    position: int = 0
    blocks_planned: int = 0
    recent: deque[TrackInfo] = field(default_factory=deque)
    last_planned: TrackInfo | None = None  # the most recently chosen song
    pending_track: TrackInfo | None = None  # song to play right after the announcement
    upcoming: asyncio.Task[_Block] | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def recent_track_ids(self) -> list[str]:
        return [t.track_id for t in self.recent]


class BroadcastPlanner:
    def __init__(
        self,
        music: MusicSource,
        director: AnnouncementDirector,
        speech: SpeechSynthesizer,
        settings: PlannerSettings | None = None,
    ) -> None:
        self.music = music
        self.director = director
        self.speech = speech
        self.settings = settings or PlannerSettings()
        self._sessions: dict[str, Session] = {}

    # --- sessions -------------------------------------------------------------

    def create_session(self, user_id: str = "guest") -> Session:
        self._evict_idle()
        if len(self._sessions) >= self.settings.max_sessions:
            raise TooManySessions(f"limit of {self.settings.max_sessions} sessions reached")
        session = Session(session_id=uuid4().hex, user_id=user_id, last_seen=time.monotonic())
        session.recent = deque(maxlen=self.settings.recent_tracks)
        self._sessions[session.session_id] = session
        logger.info("session %s created", session.session_id)
        return session

    def get_session(self, session_id: str) -> Session:
        self._evict_idle()
        try:
            return self._sessions[session_id]
        except KeyError:
            raise SessionNotFound(session_id) from None

    def close_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is None:
            raise SessionNotFound(session_id)
        self._cancel_background(session)
        logger.info("session %s closed", session_id)

    async def aclose(self) -> None:
        """Cancel all background work (call on application shutdown)."""
        sessions = list(self._sessions.values())
        self._sessions.clear()
        for session in sessions:
            self._cancel_background(session)

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    # --- the main call -----------------------------------------------------------

    async def next_segment(self, session_id: str) -> NextSegmentResponse:
        """Return the segment to play now. Never waits for speech synthesis."""
        session = self.get_session(session_id)
        async with session.lock:  # two quick /next calls must not skip a segment
            session.last_seen = time.monotonic()
            skipped: str | None = None

            if session.pending_track is not None:
                track, session.pending_track = session.pending_track, None
                segment: QueuedTrack | QueuedAnnouncement = self._track_segment(track)
            else:
                block = await self._take_block(session)
                segment, skipped = await self._resolve_block(session, block)

            session.position += 1
            if session.upcoming is None:
                session.upcoming = asyncio.create_task(self._prepare_block(session))
            return NextSegmentResponse(
                session_id=session.session_id,
                position=session.position,
                segment=segment,
                announcement_skipped=skipped,
            )

    # --- internals ---------------------------------------------------------------

    async def _take_block(self, session: Session) -> _Block:
        task, session.upcoming = session.upcoming, None
        if task is not None:
            try:
                return await asyncio.wait_for(
                    asyncio.shield(task), timeout=self.settings.music_timeout_s
                )
            # prefetch failed or is stuck: prepare again right now
            except Exception:
                task.cancel()
                logger.warning(
                    "session %s: prefetch failed, preparing now",
                    session.session_id,
                    exc_info=True,
                )
        return await self._prepare_block(session)

    async def _prepare_block(self, session: Session) -> _Block:
        index = session.blocks_planned
        session.blocks_planned += 1
        previous = session.last_planned
        track = await self._pick_track(session)
        session.recent.append(track)
        session.last_planned = track

        announcement = None
        if index > 0 and index % self.settings.songs_per_announcement == 0:
            announcement = asyncio.create_task(self._make_announcement(session, previous, track))
        return _Block(index=index, track=track, announcement=announcement)

    async def _resolve_block(
        self, session: Session, block: _Block
    ) -> tuple[QueuedTrack | QueuedAnnouncement, str | None]:
        task = block.announcement
        if task is None:
            return self._track_segment(block.track), None

        if not task.done() and self.settings.announcement_wait_s > 0:
            await asyncio.wait({task}, timeout=self.settings.announcement_wait_s)

        if task.done() and not task.cancelled() and task.exception() is None:
            announcement = task.result()
            if announcement is not None:
                session.pending_track = block.track
                return announcement, None
            reason = "announcement failed"
        else:
            reason = "announcement not ready"
            task.cancel()

        logger.warning("session %s: %s, playing the song instead", session.session_id, reason)
        return self._track_segment(block.track), reason

    async def _pick_track(self, session: Session) -> TrackInfo:
        try:
            return await asyncio.wait_for(
                self.music.next_track(
                    user_id=session.user_id, recent_track_ids=session.recent_track_ids
                ),
                timeout=self.settings.music_timeout_s,
            )
        except Exception as exc:
            fallback = self._fallback_track(session)
            if fallback is None:
                raise NoTrackAvailable("music source unavailable and nothing to replay") from exc
            logger.warning(
                "session %s: music source failed (%r), replaying %s",
                session.session_id,
                exc,
                fallback.track_id,
            )
            return fallback

    @staticmethod
    def _fallback_track(session: Session) -> TrackInfo | None:
        """A recent song, but not the one that just played (a repeat beats silence)."""
        last_id = session.last_planned.track_id if session.last_planned else None
        candidates = [t for t in session.recent if t.track_id != last_id]
        if candidates:
            return candidates[0]  # the oldest one in the history
        return session.last_planned

    async def _make_announcement(
        self, session: Session, previous: TrackInfo | None, track: TrackInfo
    ) -> QueuedAnnouncement | None:
        async def build() -> QueuedAnnouncement:
            plan = await self.director.plan(
                AnnouncementRequest(previous_track=previous, next_track=track)
            )
            audio = await self.speech.synthesize(plan)
            return QueuedAnnouncement(
                text=plan.text,
                emotion=plan.emotion,
                duration_s=audio.duration_s,
                audio_url=audio.audio_url,
                introduces_track_id=track.track_id,
            )

        try:
            return await asyncio.wait_for(build(), timeout=self.settings.announcement_timeout_s)
        # any failure: the song simply plays without an announcement
        except Exception:
            logger.warning(
                "session %s: announcement for %s failed",
                session.session_id,
                track.track_id,
                exc_info=True,
            )
            return None

    def _track_segment(self, track: TrackInfo) -> QueuedTrack:
        return QueuedTrack(
            track_id=track.track_id,
            title=track.title,
            artist=track.artist,
            license=track.license,
            reason=track.reason,
            duration_s=track.duration_s,
            audio_url=self.settings.track_audio_url.format(track_id=track.track_id),
        )

    def _evict_idle(self) -> None:
        now = time.monotonic()
        for session_id, session in list(self._sessions.items()):
            if now - session.last_seen > self.settings.session_ttl_s and not session.lock.locked():
                del self._sessions[session_id]
                self._cancel_background(session)
                logger.info("session %s expired", session_id)

    @staticmethod
    def _cancel_background(session: Session) -> None:
        task, session.upcoming = session.upcoming, None
        if task is None:
            return
        if task.done() and not task.cancelled() and task.exception() is None:
            announcement = task.result().announcement
            if announcement is not None:
                announcement.cancel()
        else:
            # the announcement task is created only when preparation finishes,
            # so cancelling an unfinished preparation leaves nothing behind
            task.cancel()
