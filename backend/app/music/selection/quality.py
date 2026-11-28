"""Quality rules shared by the song pickers (#107).

They do not decide *which mood* fits; they only choose among songs that already fit:

* Popular songs are more likely, but every candidate keeps a chance, so the same few hits
  do not loop. A song with an unknown popularity counts as average.
* After two instrumentals in a row, a sung song is preferred when one fits.
* A song does not come back within about an hour.

Popularity is not part of the four-part selection score of #23 (profile, emotion distance,
novelty, repeat penalty); it only breaks ties between songs that fit the moment.
"""

import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

# An hour of radio is about 15-18 songs (3.5 min each, with the DJ in between).
RECENT_ONE_HOUR = 18
# Listen counts are spread over 100 .. 2,000,000, so a log scale keeps the middle visible:
# 1k -> 0.48, 10k -> 0.64, 100k -> 0.80, 1M -> 0.95, 2M+ -> 1.
POPULARITY_FULL_AT = 2_000_000
# How much more often the most popular song is picked than an unknown or unpopular one.
POPULARITY_BOOST = 1.5  # weight = 1 + boost * popularity, so 1x .. 2.5x
UNKNOWN_POPULARITY = 0.5
# This many instrumentals in a row make the next pick prefer a sung song.
MAX_INSTRUMENTALS_IN_A_ROW = 2


@dataclass(frozen=True)
class TrackQuality:
    popularity: float | None = None
    has_vocals: bool | None = None


Qualities = Mapping[str, TrackQuality]


def popularity_from_listens(listens: int | None) -> float | None:
    """0..1 from a listen count on a log scale; None when the count is unknown."""
    if listens is None or listens < 0:
        return None
    return round(min(1.0, math.log10(listens + 1) / math.log10(POPULARITY_FULL_AT)), 3)


def weight(quality: TrackQuality | None) -> float:
    popularity = quality.popularity if quality and quality.popularity is not None else None
    return 1.0 + POPULARITY_BOOST * (UNKNOWN_POPULARITY if popularity is None else popularity)


def needs_vocals(recent_ids: Sequence[str], qualities: Qualities) -> bool:
    """True when the last songs were all known instrumentals."""
    last = recent_ids[-MAX_INSTRUMENTALS_IN_A_ROW:]
    if len(last) < MAX_INSTRUMENTALS_IN_A_ROW:
        return False
    return all(
        (q := qualities.get(track_id)) is not None and q.has_vocals is False for track_id in last
    )


def prefer_vocals[T](
    pool: Sequence[T], recent_ids: Sequence[str], qualities: Qualities, id_of: Callable[[T], str]
) -> list[T]:
    """The sung songs of the pool after too many instrumentals; the whole pool otherwise."""
    if not needs_vocals(recent_ids, qualities):
        return list(pool)
    sung = [t for t in pool if (q := qualities.get(id_of(t))) is not None and q.has_vocals]
    return sung or list(pool)


def weighted_choice[T](
    pool: Sequence[T], qualities: Qualities, id_of: Callable[[T], str], rng: random.Random
) -> T:
    """One item of the pool, popular songs more likely."""
    weights = [weight(qualities.get(id_of(t))) for t in pool]
    return rng.choices(list(pool), weights=weights, k=1)[0]
