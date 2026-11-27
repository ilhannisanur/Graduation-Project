"""The planner's ``AnnouncementDirector`` for song intros (#6, first version).

The planner gives only the two songs as ``TrackInfo``. The director loads the full catalog
``Track`` (valence, arousal, mood tags) and lets DJ Brain write the intro.

Not yet here: greetings by time of day, ``ListenerContext`` and other announcement kinds.
"""

import asyncio
import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.content.dj.song_intro import fallback_song_intro, generate_song_intro
from app.content.history import load_recent_announcements, save_announcement
from app.content.llm import LLMClient
from app.contracts import AnnouncementSpec, Track
from app.music.source import HistoryLoader, SessionFactory, load_history
from app.radio.planner.models import (
    AnnouncementPlan,
    AnnouncementRequest,
    RequestNote,
    TrackInfo,
)

logger = logging.getLogger(__name__)

# Same idea as HistoryLoader: tests can pass fakes instead of the database.
RecentLoader = Callable[[Session], list[str]]
AnnouncementSaver = Callable[[Session, AnnouncementSpec, str | None, bool], None]


class SongIntroDirector:
    """Implements the planner's ``AnnouncementDirector``: one song intro per request."""

    def __init__(
        self,
        llm: LLMClient,
        session_factory: SessionFactory,
        track_loader: HistoryLoader = load_history,
        recent_loader: RecentLoader = load_recent_announcements,
        saver: AnnouncementSaver = save_announcement,
    ) -> None:
        self._llm = llm
        self._session_factory = session_factory
        self._track_loader = track_loader
        self._recent_loader = recent_loader
        self._saver = saver

    async def plan(self, request: AnnouncementRequest) -> AnnouncementPlan:
        # The LLM client and the database are synchronous: keep them off the event loop.
        return await asyncio.to_thread(self._plan, request)

    def _plan(self, request: AnnouncementRequest) -> AnnouncementPlan:
        nxt = request.next_track
        if nxt.request is not None:
            # Not logged: the shout-out holds the listener's name and message.
            return shoutout_plan(nxt.request, nxt.title, nxt.artist)
        next_track, previous_track = self._load_tracks(request)
        recent = self._load_recent()
        spec = generate_song_intro(
            self._llm, next_track, previous_track, recent_announcements=recent
        )
        self._save(spec, next_track)
        return plan_from_spec(spec)

    def _load_tracks(self, request: AnnouncementRequest) -> tuple[Track, Track | None]:
        infos = [request.next_track]
        if request.previous_track is not None:
            infos.append(request.previous_track)

        with self._session_factory() as db:
            loaded = self._track_loader(db, [info.track_id for info in infos])
        by_id = {track.id: track for track in loaded}

        def full_track(info: TrackInfo) -> Track:
            return by_id.get(info.track_id) or track_from_info(info)

        previous = request.previous_track
        return full_track(request.next_track), full_track(previous) if previous else None

    def _load_recent(self) -> list[str]:
        """The log only helps: without it the DJ still talks, it may just repeat itself."""
        try:
            with self._session_factory() as db:
                return self._recent_loader(db)
        except Exception:  # the log is a side job: no error in it may silence the DJ
            logger.warning("Could not read the recent announcements", exc_info=True)
            return []

    def _save(self, spec: AnnouncementSpec, track: Track) -> None:
        """A failed save must not stop the broadcast: the announcement still airs."""
        used_fallback = spec == fallback_song_intro(track)
        try:
            with self._session_factory() as db:
                self._saver(db, spec, track.id, used_fallback)
        except Exception:  # the log is a side job: no error in it may silence the DJ
            logger.warning("Could not save the announcement", exc_info=True)


def track_from_info(info: TrackInfo) -> Track:
    """Used when a song is missing from the catalog: only title and artist are known."""
    return Track(
        id=info.track_id,
        title=info.title,
        artist=info.artist,
        duration_seconds=info.duration_s,
        license=info.license or "unknown",
        license_url="",
        source_url="",
    )


def shoutout_text(note: RequestNote) -> str:
    """The request shout-out, written here from a template, not by the LLM: names and
    messages are the listener's personal data and never go to the LLM."""
    names = note.on_air_names
    if not names:
        opening = "This one is a listener request."
    elif len(names) == 1:
        opening = f"This one goes out to {names[0]}, who asked for it."
    else:
        opening = f"This one goes out to {', '.join(names[:-1])} and {names[-1]}."
    if note.messages:
        message = note.messages[0].strip().rstrip(".!?")
        opening += f' The message says: "{message}."'
    return opening


def shoutout_plan(note: RequestNote, title: str, artist: str) -> AnnouncementPlan:
    """A request is announced with the shout-out and a short intro, without the LLM.

    Short on purpose: on a laptop GPU every word adds voicing time, and the listener who
    asked is waiting for it. Happy, at an intensity below 0.5: Orpheus adds no laugh tags
    there, which sounded squeaky in our tests.
    """
    return AnnouncementPlan(
        text=f"{shoutout_text(note)} Here is {title} by {artist}.",
        emotion="happy",
        intensity=0.4,
    )


def plan_from_spec(spec: AnnouncementSpec) -> AnnouncementPlan:
    """Convert DJ Brain's contract type to the planner's model."""
    return AnnouncementPlan(
        text=spec.text,
        emotion=spec.emotion.value,
        target_duration_s=spec.target_seconds,
    )
