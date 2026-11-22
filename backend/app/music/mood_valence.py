"""First valence/energy estimate for a track, taken from its MTG-Jamendo mood tags.

Valence is how positive the music feels (0 = negative, 1 = positive). Energy is how intense it is
(0 = very calm, 1 = very intense); it is stored in `tracks.arousal`. Both are in [0, 1].

This is a rough, tag-only estimate that works until the audio model (#20) replaces it. The table
below and its reasoning are written up in docs/duygu-muzik-esleme.md; keep the two in sync.
"""

from collections.abc import Iterable

# tag -> (valence, energy). Every tag in the current 400-track catalog has an entry.
TAG_VALENCE_ENERGY: dict[str, tuple[float, float]] = {
    # Positive and lively
    "happy": (0.85, 0.65),
    "upbeat": (0.80, 0.75),
    "positive": (0.80, 0.55),
    "uplifting": (0.80, 0.60),
    "fun": (0.80, 0.70),
    "funny": (0.75, 0.60),
    "party": (0.80, 0.90),
    "groovy": (0.70, 0.70),
    "summer": (0.75, 0.65),
    "children": (0.80, 0.55),
    "game": (0.60, 0.70),
    # Hopeful and driven
    "hopeful": (0.70, 0.45),
    "inspiring": (0.75, 0.55),
    "motivational": (0.75, 0.70),
    "adventure": (0.60, 0.75),
    "travel": (0.65, 0.50),
    "cool": (0.60, 0.55),
    "sexy": (0.65, 0.50),
    # Intense
    "energetic": (0.65, 0.90),
    "powerful": (0.50, 0.90),
    "action": (0.45, 0.90),
    "fast": (0.55, 0.90),
    "epic": (0.50, 0.85),
    "trailer": (0.40, 0.80),
    # Tense and dark
    "dark": (0.15, 0.50),
    "dramatic": (0.30, 0.70),
    "drama": (0.30, 0.65),
    "horror": (0.08, 0.75),
    # Sad and slow
    "sad": (0.12, 0.25),
    "melancholic": (0.20, 0.25),
    "emotional": (0.35, 0.40),
    "ballad": (0.35, 0.30),
    "slow": (0.40, 0.15),
    "deep": (0.35, 0.30),
    # Calm and gentle
    "calm": (0.60, 0.10),
    "relaxing": (0.65, 0.12),
    "soft": (0.60, 0.15),
    "meditative": (0.55, 0.08),
    "mellow": (0.60, 0.20),
    "dream": (0.65, 0.20),
    "nature": (0.65, 0.20),
    "soundscape": (0.50, 0.15),
    "romantic": (0.75, 0.30),
    "love": (0.80, 0.35),
    "melodic": (0.60, 0.40),
    # Theme tags: weak signal, placed near the middle
    "christmas": (0.75, 0.45),
    "holiday": (0.75, 0.45),
    "documentary": (0.45, 0.35),
    "film": (0.45, 0.50),
    "movie": (0.45, 0.50),
    "space": (0.50, 0.35),
    "background": (0.50, 0.25),
    "corporate": (0.65, 0.45),
    "advertising": (0.65, 0.50),
    "commercial": (0.65, 0.50),
}

# Written to `tracks.affect_source` so values can be compared with the audio model (#20) later.
SOURCE_TAGS = "tags"


def estimate_valence_energy(tags: Iterable[str]) -> tuple[float, float] | None:
    """Mean (valence, energy) over the tags we know; None if the track has none of them."""
    known = [TAG_VALENCE_ENERGY[tag] for tag in tags if tag in TAG_VALENCE_ENERGY]
    if not known:
        return None
    valence = sum(v for v, _ in known) / len(known)
    energy = sum(e for _, e in known) / len(known)
    return round(valence, 3), round(energy, 3)
