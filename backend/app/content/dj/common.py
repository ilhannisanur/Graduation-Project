from typing import Any

from app.contracts import AnnouncementKind, AnnouncementSpec, Emotion

WORDS_PER_SECOND = 2.5
MIN_SECONDS = 3.0
MAX_SECONDS = 120.0  # upper limit of AnnouncementSpec.target_seconds


def seconds_for(text: str) -> float:
    """Expected speaking time of a text, kept inside the contract's limits."""
    seconds = len(text.split()) / WORDS_PER_SECOND
    return min(MAX_SECONDS, max(MIN_SECONDS, seconds))


def spec_from_answer(answer: Any, kind: AnnouncementKind) -> AnnouncementSpec | None:
    """Check the LLM answer; return None if it cannot be used."""
    if not isinstance(answer, dict):
        return None
    text = answer.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    emotion_name = answer.get("emotion")
    if not isinstance(emotion_name, str):
        return None
    try:
        emotion = Emotion(emotion_name.strip().lower())  # "Happy " is fine too
    except ValueError:
        return None
    text = text.strip()
    return AnnouncementSpec(
        kind=kind,
        text=text,
        emotion=emotion,
        target_seconds=seconds_for(text),
    )
