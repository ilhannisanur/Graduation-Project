from datetime import datetime
from typing import Any

from app.content.llm import LLMClient, LLMError
from app.contracts import AnnouncementKind, AnnouncementSpec, Emotion

WORDS_PER_SECOND = 2.5
MIN_SECONDS = 3.0
MAX_SECONDS = 120.0  # upper limit of AnnouncementSpec.target_seconds

# One more try when the LLM answer is unusable (bad emotion or empty text).
LLM_ATTEMPTS = 2


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


def ask_llm_for_spec(
    llm: LLMClient, prompt: str, system: str, kind: AnnouncementKind
) -> AnnouncementSpec | None:
    """Ask the LLM for an announcement; try once more on an unusable answer. None if it fails."""
    for _ in range(LLM_ATTEMPTS):
        try:
            answer = llm.generate_json(prompt, system=system)
        except LLMError:
            # Timeouts and server errors are already retried inside the client (#52).
            break
        spec = spec_from_answer(answer, kind)
        if spec is not None:
            return spec
    return None


def describe_day_part(now: datetime) -> str:
    """Turn a time into words such as "Friday evening"."""
    hour = now.hour
    if 5 <= hour < 12:
        part = "morning"
    elif 12 <= hour < 17:
        part = "afternoon"
    elif 17 <= hour < 21:
        part = "evening"
    else:
        part = "night"
    return f"{now.strftime('%A')} {part}"
