"""Pick songs by a target mood on the valence/energy plane (first step of #23).

The station's mood is a point: valence (0 = sad, 1 = happy) and energy (0 = calm, 1 = intense),
the same scale as `tracks.valence` / `tracks.arousal` (#75). The song closest to that point is
a good fit; one of the few closest is picked at random so the radio does not repeat itself.

The target lives in memory for the whole station (there is one shared broadcast). It is set
from the studio screen (POST /api/station/mood); None means "no target": random selection.
"""

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts import Track
from app.music.convert import track_from_row
from app.music.models import TrackRow

# Pick among this many of the closest songs.
CLOSEST = 6
# These many latest songs may not come back.
RECENT_LIMIT = 12


@dataclass(frozen=True)
class MoodTarget:
    id: str
    label: str
    valence: float
    energy: float
    # Shown to listeners as "why this song?"; {title} is the picked song.
    reason: str


PRESETS: dict[str, MoodTarget] = {
    target.id: target
    for target in [
        MoodTarget(
            "sunny-morning", "Sunny morning", 0.85, 0.65, "a bright, happy song for a sunny morning"
        ),
        MoodTarget(
            "rainy-evening", "Rainy evening", 0.35, 0.18, "a slow, gentle song for a rainy evening"
        ),
        MoodTarget("calm", "Calm down", 0.62, 0.1, "something calm to slow things down"),
        MoodTarget("party", "Party time", 0.78, 0.9, "high energy to lift the room"),
        MoodTarget("melancholy", "Melancholy", 0.12, 0.25, "a sad song for a heavy-hearted moment"),
        MoodTarget("tense", "Tense news", 0.18, 0.62, "a darker, tense mood after serious news"),
    ]
}

_current: MoodTarget | None = None


def current_target() -> MoodTarget | None:
    return _current


def set_target(target_id: str | None) -> MoodTarget | None:
    """Set the station's mood; None clears it. Raises KeyError for an unknown id."""
    global _current
    _current = PRESETS[target_id] if target_id is not None else None
    return _current


def distance(track: Track, target: MoodTarget) -> float:
    return math.dist((track.valence or 0.0, track.arousal or 0.0), (target.valence, target.energy))


def choose_for_target(
    candidates: Sequence[Track],
    recent_ids: Sequence[str],
    target: MoodTarget,
    rng: random.Random,
) -> Track | None:
    """One of the songs closest to the target, not played recently. None if none has values."""
    recent = set(recent_ids[-RECENT_LIMIT:])
    scored = [t for t in candidates if t.valence is not None and t.arousal is not None]
    fresh = [t for t in scored if t.id not in recent] or scored
    if not fresh:
        return None
    fresh.sort(key=lambda t: distance(t, target))
    return rng.choice(fresh[:CLOSEST])


def pick_for_target(
    db: Session, recent_ids: Sequence[str], target: MoodTarget, rng: random.Random
) -> Track | None:
    rows = db.scalars(
        select(TrackRow).where(TrackRow.valence.is_not(None), TrackRow.arousal.is_not(None))
    )
    return choose_for_target([track_from_row(r) for r in rows], recent_ids, target, rng)
