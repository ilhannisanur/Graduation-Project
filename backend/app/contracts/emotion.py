"""The single source of truth for the emotion list used across the project."""

from enum import StrEnum


class Emotion(StrEnum):
    """Mood of an announcement or a moment. Serialized as lowercase text, e.g. "happy"."""

    HAPPY = "happy"
    SAD = "sad"
    EXCITED = "excited"
    CALM = "calm"
    SERIOUS = "serious"
    SURPRISED = "surprised"
    NEUTRAL = "neutral"
