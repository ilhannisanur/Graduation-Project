import random
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.content.dj.prompts import load_prompt
from app.content.llm import LLMClient, LLMError
from app.contracts import AnnouncementKind, AnnouncementSpec, Emotion, Track

WORDS_PER_SECOND = 2.5
MIN_SECONDS = 3.0
MAX_SECONDS = 120.0  # upper limit of AnnouncementSpec.target_seconds

# Each announcement gets a random word limit in this range, so lengths vary.
MIN_WORDS = 12
MAX_WORDS = 50
# How often the day/time and the previous song are given to the LLM.
# Giving them every time makes every announcement mention them.
DAY_PART_PROBABILITY = 0.5
PREVIOUS_SONG_PROBABILITY = 0.5
# One more try when the LLM answer is unusable (bad emotion or empty text).
LLM_ATTEMPTS = 2

DEFAULT_TIMEZONE = ZoneInfo("Europe/Istanbul")


def fallback_song_intro(track: Track) -> AnnouncementSpec:
    """Template announcement used when the LLM fails or times out."""
    text = f"Up next, {track.title} by {track.artist}."
    return AnnouncementSpec(
        kind=AnnouncementKind.SONG_INTRO,
        text=text,
        emotion=Emotion.NEUTRAL,
        target_seconds=_seconds_for(text),
    )


def build_song_intro_prompt(
    next_track: Track,
    max_words: int,
    previous_track: Track | None = None,
    day_part: str | None = None,
    recent_announcements: Sequence[str] = (),
) -> str:
    """Build the per-request prompt for a song intro.

    Only the information that is given gets a line; a missing field is left out.
    The fixed rules live in the song_intro system prompt.
    """
    lines = [f'Next song: "{next_track.title}" by {next_track.artist}']

    if next_track.valence is not None and next_track.arousal is not None:
        lines.append(f"Valence: {next_track.valence:.2f}, arousal: {next_track.arousal:.2f}")

    # The planner replays the same song when the music source is down.
    if previous_track is not None and previous_track.id != next_track.id:
        lines.append(f'Song that just played: "{previous_track.title}" by {previous_track.artist}')

    if day_part:
        lines.append(f"Day and time of day: {day_part}")

    lines.append(f"Maximum words: {max_words}")

    if recent_announcements:
        lines.append("Your most recent announcements:")
        for number, text in enumerate(recent_announcements, start=1):
            lines.append(f"{number}. {text}")

    return "\n".join(lines)


def generate_song_intro(
    llm: LLMClient,
    next_track: Track,
    previous_track: Track | None = None,
    recent_announcements: Sequence[str] = (),
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> AnnouncementSpec:
    """Write a song intro with the LLM. Never raises: falls back to a template.

    ``now`` and ``rng`` can be given so tests get the same result every run.
    """
    rng = rng or random.Random()
    now = now or datetime.now(DEFAULT_TIMEZONE)

    max_words = rng.randint(MIN_WORDS, MAX_WORDS)
    give_day_part = rng.random() < DAY_PART_PROBABILITY
    give_previous = rng.random() < PREVIOUS_SONG_PROBABILITY

    prompt = build_song_intro_prompt(
        next_track,
        max_words,
        previous_track=previous_track if give_previous else None,
        day_part=describe_day_part(now) if give_day_part else None,
        recent_announcements=recent_announcements,
    )
    system = load_prompt("song_intro")

    for _ in range(LLM_ATTEMPTS):
        try:
            answer = llm.generate_json(prompt, system=system)
        except LLMError:
            # Timeouts and server errors are already retried inside the client (#52).
            break
        spec = _spec_from_answer(answer)
        if spec is not None:
            return spec

    return fallback_song_intro(next_track)


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


def _spec_from_answer(answer: Any) -> AnnouncementSpec | None:
    """Check the LLM answer; return None if it cannot be used."""
    if not isinstance(answer, dict):
        return None
    text = answer.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        emotion = Emotion(answer.get("emotion"))
    except ValueError:
        return None
    text = text.strip()
    return AnnouncementSpec(
        kind=AnnouncementKind.SONG_INTRO,
        text=text,
        emotion=emotion,
        target_seconds=_seconds_for(text),
    )


def _seconds_for(text: str) -> float:
    """Expected speaking time of a text, kept inside the contract's limits."""
    seconds = len(text.split()) / WORDS_PER_SECOND
    return min(MAX_SECONDS, max(MIN_SECONDS, seconds))
