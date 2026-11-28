"""The planner's ``AnnouncementDirector`` for song intros (#6, first version).

The planner gives only the two songs as ``TrackInfo``. The director loads the full catalog
``Track`` (valence, arousal, mood tags) and lets DJ Brain write the intro.

Not yet here: greetings by time of day, ``ListenerContext`` and other announcement kinds.
"""

import asyncio
import random

from app.content.dj.song_intro import generate_song_intro
from app.content.llm import LLMClient
from app.contracts import AnnouncementSpec, Track
from app.music.source import HistoryLoader, SessionFactory, load_history
from app.radio.planner.models import (
    AnnouncementPlan,
    AnnouncementRequest,
    RequestNote,
    TrackInfo,
)


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
        nxt = request.next_track
        if nxt.request is not None:
            return shoutout_plan(nxt.request, nxt.title, nxt.artist)
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


# Shout-out openings. One is picked at random so the DJ does not say the same line every time.
SHOUTOUT_ANONYMOUS = (
    "This one is a listener request.",
    "A listener asked for this one.",
    "Next up, a song one of you requested.",
    "This one comes straight from our request line.",
    "Somebody out there wanted to hear this one.",
    "Here is a request from one of our listeners.",
)
SHOUTOUT_ONE = (
    "This one goes out to {name}, who asked for it.",
    "{name}, this one is for you.",
    "{name} asked for this one, so here it comes.",
    "A request from {name} is up next.",
    "Big hello to {name}, this one is your pick.",
    "This next song is for {name}.",
)
SHOUTOUT_MANY = (
    "This one goes out to {names}.",
    "{names}, this one is for you.",
    "{names} all asked for this one.",
    "A shout-out to {names}, who requested this one.",
    "This next song is for {names}.",
    "Hello to {names}, this one is your pick.",
)
SHOUTOUT_MESSAGE = (
    ' The message says: "{message}."',
    ' And the message reads: "{message}."',
    ' They wrote: "{message}."',
)


def shoutout_text(note: RequestNote, rng: random.Random | None = None) -> str:
    """The request shout-out, written here from a template, not by the LLM: names and
    messages are the listener's personal data and never go to the LLM."""
    pick = (rng or random).choice
    names = note.on_air_names
    if not names:
        opening = pick(SHOUTOUT_ANONYMOUS)
    elif len(names) == 1:
        opening = pick(SHOUTOUT_ONE).format(name=names[0])
    else:
        opening = pick(SHOUTOUT_MANY).format(names=f"{', '.join(names[:-1])} and {names[-1]}")
    if note.messages:
        message = note.messages[0].strip().rstrip(".!?")
        opening += pick(SHOUTOUT_MESSAGE).format(message=message)
    return opening


def shoutout_plan(
    note: RequestNote, title: str, artist: str, rng: random.Random | None = None
) -> AnnouncementPlan:
    """A request is announced with the shout-out and a short intro, without the LLM.

    Short on purpose: on a laptop GPU every word adds voicing time, and the listener who
    asked is waiting for it. Happy, at an intensity below 0.5: Orpheus adds no laugh tags
    there, which sounded squeaky in our tests.
    """
    return AnnouncementPlan(
        text=f"{shoutout_text(note, rng)} Here is {title} by {artist}.",
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
