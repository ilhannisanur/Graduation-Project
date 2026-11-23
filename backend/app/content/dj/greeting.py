import random
from collections.abc import Sequence
from datetime import datetime

from app.content.dj.common import (
    DEFAULT_TIMEZONE,
    ask_llm_for_spec,
    describe_day_part,
    recent_lines,
    seconds_for,
    track_lines,
)
from app.content.dj.prompts import load_prompt
from app.content.llm import LLMClient
from app.contracts import AnnouncementKind, AnnouncementSpec, Emotion, Track

# Each greeting gets a random word limit in this range, so lengths vary.
MIN_WORDS = 15
MAX_WORDS = 50


HOUR_WORDS = [
    "twelve",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
]


ON_THE_HOUR = "{} o'clock"

# (the minute is below this number, phrase, hours to add)
TIME_PHRASES = [
    (6, ON_THE_HOUR, 0),
    (13, "just after {}", 0),
    (23, "quarter past {}", 0),
    (38, "half past {}", 0),
    (48, "quarter to {}", 1),
    (55, "almost {}", 1),
    (60, ON_THE_HOUR, 1),
]


TIME_PLACEHOLDER = "{time}"
STATION_PLACEHOLDER = "{station}"


def hour_name(hour: int) -> str:
    """Say an hour (0-24) the way a DJ would: 'nine', 'midnight', 'noon'."""
    hour = hour % 24
    if hour == 0:
        return "midnight"
    if hour == 12:
        return "noon"
    return HOUR_WORDS[hour % 12]


def spoken_time(now: datetime) -> str:
    """Say the time the way a DJ would, for example 'half past nine'."""
    for end_minute, phrase, hour_offset in TIME_PHRASES:
        if now.minute < end_minute:
            name = hour_name(now.hour + hour_offset)
            if phrase == ON_THE_HOUR and name in ("midnight", "noon"):
                return name
            return phrase.format(name)


def has_placeholders(text: str) -> bool:
    """True if the text has {time} and {station} exactly once each."""
    return text.count(TIME_PLACEHOLDER) == 1 and text.count(STATION_PLACEHOLDER) == 1


def build_greeting_prompt(
    next_track: Track,
    max_words: int,
    day_part: str,
    recent_announcements: Sequence[str] = (),
) -> str:
    """Build the per-greeting prompt. The fixed rules live in the greeting system prompt."""
    lines = track_lines(next_track)
    lines.append(f"Day and time of day: {day_part}")
    lines.append(f"Maximum words: {max_words}")
    lines.extend(recent_lines(recent_announcements))
    return "\n".join(lines)


def fallback_greeting(next_track: Track, now: datetime, station: str) -> AnnouncementSpec:
    """Template greeting used when the LLM fails or times out."""
    text = (
        f"It's {spoken_time(now)} on {station}. Up next, {next_track.title} by {next_track.artist}."
    )
    return AnnouncementSpec(
        kind=AnnouncementKind.GREETING,
        text=text,
        emotion=Emotion.NEUTRAL,
        target_seconds=seconds_for(text),
    )


def fill_placeholders(spec: AnnouncementSpec, now: datetime, station: str) -> AnnouncementSpec:
    """Put the spoken time and the station name into the LLM's greeting."""
    text = spec.text.replace(TIME_PLACEHOLDER, spoken_time(now))
    text = text.replace(STATION_PLACEHOLDER, station)
    return spec.model_copy(update={"text": text, "target_seconds": seconds_for(text)})


def generate_greeting(
    llm: LLMClient,
    next_track: Track,
    station: str,
    recent_announcements: Sequence[str] = (),
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> AnnouncementSpec:
    """Write a greeting with the LLM. Never raises: falls back to a template."""
    rng = rng or random.Random()
    now = now or datetime.now(DEFAULT_TIMEZONE)

    prompt = build_greeting_prompt(
        next_track,
        rng.randint(MIN_WORDS, MAX_WORDS),
        describe_day_part(now),
        recent_announcements,
    )
    system = load_prompt("greeting")

    spec = ask_llm_for_spec(llm, prompt, system, AnnouncementKind.GREETING, check=has_placeholders)
    if spec is None:
        return fallback_greeting(next_track, now, station)
    return fill_placeholders(spec, now, station)
