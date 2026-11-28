import random
from collections.abc import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts import Emotion, Track
from app.music.convert import track_from_row
from app.music.models import TrackRow
from app.music.selection.base import NoTrackAvailable, TrackSelector
from app.music.selection.mood_map import tags_for
from app.music.selection.quality import (
    RECENT_ONE_HOUR,
    Qualities,
    TrackQuality,
    prefer_vocals,
    weighted_choice,
)

RECENT_LIMIT = RECENT_ONE_HOUR  # how many of the latest songs may not come back


def choose_track(
    candidates: Sequence[Track],
    history: Sequence[Track],
    emotion: Emotion | None,
    rng: random.Random,
    recent_limit: int = RECENT_LIMIT,
    qualities: Qualities | None = None,
) -> Track:
    """Random pick that fits the mood and avoids repeats.

    The rules are relaxed step by step when nothing is left, so the radio never goes silent:
    mood and repeat rules -> repeat rules only -> only "not the song just played" -> anything.
    With `qualities`, popular songs are more likely and a sung song follows two instrumentals.
    """
    if not candidates:
        raise NoTrackAvailable("The catalog is empty.")

    recent = history[-recent_limit:] if recent_limit > 0 else []
    recent_ids = {t.id for t in recent}
    last = history[-1] if history else None
    wanted = tags_for(emotion)

    def fits_mood(t: Track) -> bool:
        return not wanted or bool(wanted & set(t.mood_tags))

    def fresh(t: Track) -> bool:
        return t.id not in recent_ids and (last is None or t.artist != last.artist)

    steps: list[Callable[[Track], bool]] = [
        lambda t: fits_mood(t) and fresh(t),
        fresh,
        lambda t: last is None or t.id != last.id,
        lambda t: True,
    ]
    for rule in steps:
        pool = [t for t in candidates if rule(t)]
        if pool:
            if qualities is None:
                return rng.choice(pool)
            history_ids = [t.id for t in history]
            pool = prefer_vocals(pool, history_ids, qualities, lambda t: t.id)
            return weighted_choice(pool, qualities, lambda t: t.id, rng)
    raise AssertionError("unreachable: the last rule accepts every candidate")


class RandomSelector(TrackSelector):
    """First selector: mood filter + random choice from the database catalog."""

    def __init__(
        self,
        db: Session,
        rng: random.Random | None = None,
        recent_limit: int = RECENT_LIMIT,
    ) -> None:
        self.db = db
        self.rng = rng or random.Random()
        self.recent_limit = recent_limit

    def next_track(self, history: Sequence[Track], emotion: Emotion | None = None) -> Track:
        # Only playable tracks (with an audio file) are candidates.
        rows = list(self.db.scalars(select(TrackRow).where(TrackRow.file_path.is_not(None))))
        candidates = [track_from_row(row) for row in rows]
        qualities = {r.id: TrackQuality(r.popularity, r.has_vocals) for r in rows}
        return choose_track(
            candidates, history, emotion, self.rng, self.recent_limit, qualities=qualities
        )
