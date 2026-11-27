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

# Each announcement gets a random word limit in this range, so lengths vary.
MIN_WORDS = 12
MAX_WORDS = 50
# How often the day/time and the previous song are given to the LLM.
# Giving them every time makes every announcement mention them.
DAY_PART_PROBABILITY = 0.5
PREVIOUS_SONG_PROBABILITY = 0.5


# Template intros by the song's mood, used when the LLM is unavailable, so the DJ still sounds
# like the music. {t} is the title, {a} the artist.
# Written like full spoken sentences: short shouted lines sound rushed and robotic in TTS.
MOOD_TEMPLATES: dict[Emotion, tuple[str, ...]] = {
    Emotion.EXCITED: (
        "Okay, I've got a really fun one for you. This is {t} by {a}, so go ahead and turn it up.",
        "Let's bring the energy back up. Here's {t} by {a}, and it's a great one.",
        "If you need a little push right now, this is it. Coming up, {t} by {a}.",
    ),
    Emotion.HAPPY: (
        "Here's something that always makes me smile. This is {t} by {a}.",
        "A bright, happy one for you now. Enjoy {t} by {a}.",
        "This one should put a little spring in your step. It's {t}, by {a}.",
    ),
    Emotion.CALM: (
        "Let's take it easy for a moment. This is {t} by {a}.",
        "Take a breath and settle in. Here's {t} by {a}.",
        "Something soft and gentle for you now. This is {t}, by {a}.",
    ),
    Emotion.SAD: (
        "A quieter moment now. This is {t} by {a}.",
        "Here's a tender one, with a lot of heart. This is {t} by {a}.",
        "This next one has a heavy heart, but it's beautiful. {t}, by {a}.",
    ),
    Emotion.SERIOUS: (
        "The mood gets a little darker now. Listen closely to {t} by {a}.",
        "Here's something more intense and dramatic. This is {t} by {a}.",
        "Things get a little heavier now. Coming up, {t} by {a}.",
    ),
}


def mood_emotion(valence: float, energy: float) -> Emotion:
    """The DJ's emotion for a song's place on the valence/energy plane (#75 values)."""
    if valence >= 0.6:
        if energy >= 0.65:
            return Emotion.EXCITED
        return Emotion.HAPPY if energy >= 0.35 else Emotion.CALM
    if valence < 0.35:
        return Emotion.SAD if energy < 0.45 else Emotion.SERIOUS
    return Emotion.CALM if energy < 0.35 else Emotion.NEUTRAL


def fallback_song_intro(track: Track) -> AnnouncementSpec:
    """Template announcement used when the LLM fails or times out.

    With the song's valence and energy known, the emotion and wording follow its mood; the
    template is picked from the track id, so the same song always gets the same fallback.
    """
    emotion = Emotion.NEUTRAL
    text = f"Up next, {track.title} by {track.artist}."
    if track.valence is not None and track.arousal is not None:
        emotion = mood_emotion(track.valence, track.arousal)
        templates = MOOD_TEMPLATES.get(emotion)
        if templates:
            choice = sum(map(ord, track.id)) % len(templates)
            text = templates[choice].format(t=track.title, a=track.artist)
    return AnnouncementSpec(
        kind=AnnouncementKind.SONG_INTRO,
        text=text,
        emotion=emotion,
        target_seconds=seconds_for(text),
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
    lines = track_lines(next_track)

    # The planner replays the same song when the music source is down.
    if previous_track is not None and previous_track.id != next_track.id:
        lines.append(f'Song that just played: "{previous_track.title}" by {previous_track.artist}')

    if day_part:
        lines.append(f"Day and time of day: {day_part}")

    lines.append(f"Maximum words: {max_words}")

    lines.extend(recent_lines(recent_announcements))

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

    spec = ask_llm_for_spec(llm, prompt, system, AnnouncementKind.SONG_INTRO)
    return spec or fallback_song_intro(next_track)
