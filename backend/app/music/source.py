"""Adapter that lets the broadcast planner (#9) use our track selection (#11).

The planner asks for "the next song" with ids only; the selector works with ``Track``
objects and a database session. This class converts between the two (#12).
"""

import asyncio
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session

from app.contracts import Track
from app.music.convert import track_from_row
from app.music.models import TrackRow
from app.music.selection import RandomSelector, TrackSelector
from app.radio.planner.models import TrackInfo

SessionFactory = Callable[[], AbstractContextManager[Session]]
SelectorFactory = Callable[[Session], TrackSelector]
HistoryLoader = Callable[[Session, Sequence[str]], list[Track]]


def load_history(db: Session, track_ids: Sequence[str]) -> list[Track]:
    """Catalog tracks for the given ids, in the same order. Unknown ids are skipped."""
    rows = (db.get(TrackRow, track_id) for track_id in track_ids)
    return [track_from_row(row) for row in rows if row is not None]


def track_info_from_track(track: Track) -> TrackInfo:
    return TrackInfo(
        track_id=track.id,
        title=track.title,
        artist=track.artist,
        duration_s=track.duration_seconds,
        license=track.license,
    )


class CatalogMusicSource:
    """Implements the planner's ``MusicSource`` on top of a ``TrackSelector``.

    Raises ``app.music.selection.NoTrackAvailable`` when the catalog is empty; the planner
    then replays a recent song instead of going silent.

    The listener's profile (genres, artists, languages) is not used yet: ``TrackSelector``
    has no profile parameter and catalog tracks carry no genre or language. ``user_id`` is
    accepted so the profile can be added later without changing the planner.
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        selector_factory: SelectorFactory = RandomSelector,
        history_loader: HistoryLoader = load_history,
    ) -> None:
        self._session_factory = session_factory
        self._selector_factory = selector_factory
        self._history_loader = history_loader

    async def next_track(self, *, user_id: str, recent_track_ids: Sequence[str]) -> TrackInfo:
        # The database and the selector are synchronous: keep them off the event loop.
        return await asyncio.to_thread(self._pick, list(recent_track_ids))

    def _pick(self, recent_track_ids: list[str]) -> TrackInfo:
        with self._session_factory() as db:
            history = self._history_loader(db, recent_track_ids)
            track = self._selector_factory(db).next_track(history)
        return track_info_from_track(track)
