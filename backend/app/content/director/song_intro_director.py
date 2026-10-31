"""The planner's ``AnnouncementDirector`` for song intros (#6, first version).

The planner gives only the two songs as ``TrackInfo``. The director loads the full catalog
``Track`` (valence, arousal, mood tags) and lets DJ Brain write the intro.

Not yet here: greetings by time of day, ``ListenerContext`` and other announcement kinds.
"""

import asyncio

from app.content.dj.song_intro import generate_song_intro
from app.content.llm import LLMClient
from app.contracts import AnnouncementSpec, Track
from app.music.source import HistoryLoader, SessionFactory, load_history
from app.radio.planner.models import AnnouncementPlan, AnnouncementRequest, TrackInfo


class SongIntroDirector:
    """Implements the planner's ``AnnouncementDirector``: one song intro per request."""

    def __init__(
        self,
        llm: LLMClient,
        session_factory: SessionFactory,
        track_loader: HistoryLoader = load_history,
    ) -> None:
        self._llm = llm
        self._session_factory = session_factory
        self._track_loader = track_loader

    async def plan(self, request: AnnouncementRequest) -> AnnouncementPlan:
        # The LLM client and the database are synchronous: keep them off the event loop.
        return await asyncio.to_thread(self._plan, request)

    def _plan(self, request: AnnouncementRequest) -> AnnouncementPlan:
        next_track, previous_track = self._load_tracks(request)
        spec = generate_song_intro(self._llm, next_track, previous_track)
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


def plan_from_spec(spec: AnnouncementSpec) -> AnnouncementPlan:
    """Convert DJ Brain's contract type to the planner's model."""
    return AnnouncementPlan(
        text=spec.text,
        emotion=spec.emotion.value,
        target_duration_s=spec.target_seconds,
    )
