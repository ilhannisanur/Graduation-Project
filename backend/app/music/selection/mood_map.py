"""Which catalog mood tags suit which emotion.

The tags are the Jamendo/MTG labels stored in `Track.mood_tags`. This is the first, tag-only
version; valence/arousal targets are added with the personal selector (#23).
"""

from app.contracts import Emotion

EMOTION_TAGS: dict[Emotion, frozenset[str]] = {
    Emotion.HAPPY: frozenset({"happy", "upbeat", "positive", "uplifting", "fun"}),
    Emotion.SAD: frozenset({"sad", "melancholic", "emotional", "ballad"}),
    Emotion.EXCITED: frozenset({"energetic", "upbeat", "powerful", "action", "party"}),
    Emotion.CALM: frozenset({"calm", "relaxing", "soft", "meditative", "mellow"}),
    Emotion.SERIOUS: frozenset({"dark", "dramatic", "epic", "documentary"}),
    # The catalog has no "surprising" tag; lively and dramatic music is the closest fit.
    Emotion.SURPRISED: frozenset({"energetic", "dramatic", "adventure", "fun"}),
    # Neutral means "no preference": no filter.
    Emotion.NEUTRAL: frozenset(),
}


def tags_for(emotion: Emotion | None) -> frozenset[str]:
    """Tags that fit the emotion; empty means any track fits."""
    return EMOTION_TAGS.get(emotion, frozenset()) if emotion else frozenset()
