"""The music source the broadcast planner uses: requests first, then the station's mood.

Order of choice for the next song:

1. The listener request queue (#16): the next requested song. Requests for the same song are
   merged, so the song plays once for everyone who asked.
2. The station's mood target (app.music.mood_target), if one is set: a song close to it on
   the valence/energy plane, with the reason shown as "why this song?".
3. Otherwise the regular catalog source (random, mood tags).
"""

import asyncio
import random
from collections.abc import Sequence

from app.music.convert import track_from_row
from app.music.models import TrackRow
from app.music.mood_target import current_target, pick_for_target
from app.music.requests import service as requests
from app.music.source import CatalogMusicSource, SessionFactory, track_info_from_track
from app.radio.planner.models import RequestNote, TrackInfo


class BroadcastMusicSource:
    """Implements the planner's ``MusicSource``."""

    def __init__(
        self,
        session_factory: SessionFactory,
        fallback: CatalogMusicSource | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._fallback = fallback or CatalogMusicSource(session_factory)
        self._rng = rng or random.Random()
        # Requested tracks put in line by the planner that have not started yet. Their
        # requests stay "accepted" (and in the public queue) until the song is on air.
        self._on_deck: set[str] = set()

    async def next_track(self, *, user_id: str, recent_track_ids: Sequence[str]) -> TrackInfo:
        picked = await asyncio.to_thread(self._pick, list(recent_track_ids))
        if picked is not None:
            return picked
        return await self._fallback.next_track(user_id=user_id, recent_track_ids=recent_track_ids)

    def _pick(self, recent_track_ids: list[str]) -> TrackInfo | None:
        with self._session_factory() as db:
            group = requests.next_group(db, skip_track_ids=self._on_deck)
            if group:
                row = db.get(TrackRow, group[0].track_id)
                if row is not None:
                    self._on_deck.add(row.id)
                    return self._request_info(track_from_row(row), group)

            target = current_target()
            if target is not None:
                track = pick_for_target(db, recent_track_ids, target, self._rng)
                if track is not None:
                    info = track_info_from_track(track)
                    info.reason = target.reason.capitalize()
                    return info
        return None

    async def track_started(self, track_id: str) -> None:
        """The planner put a requested song on air: its requests are played now."""
        await asyncio.to_thread(self._mark_played, track_id)

    def _mark_played(self, track_id: str) -> None:
        with self._session_factory() as db:
            requests.mark_played(db, track_id)
            db.commit()
        self._on_deck.discard(track_id)

    @staticmethod
    def _request_info(track, group) -> TrackInfo:
        names = list(dict.fromkeys(r.on_air_name for r in group if r.on_air_name))
        messages = [m for r in group if (m := requests.shoutout_message(r))]
        info = track_info_from_track(track)
        count = len(group)
        info.reason = (
            f"Requested by {', '.join(names)}"
            if names
            else f"Requested by {count} listener{'s' if count > 1 else ''}"
        )
        info.request = RequestNote(on_air_names=names, messages=messages)
        return info
