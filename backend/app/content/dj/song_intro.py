import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

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


class OpeningStyle(StrEnum):
    """How the DJ starts the intro (#74). Python picks one, the LLM follows it."""

    ARTIST_LEAD = "artist_lead"
    MOOD_LEAD = "mood_lead"
    PREVIOUS_TRACK = "previous_track"
    LISTENER = "listener"
    DIRECT = "direct"
    TIME_OF_DAY = "time_of_day"


class TitlePlacement(StrEnum):
    """Where the song title goes: varied so most intros do not end with "Title by Artist"."""

    START = "start"
    END = "end"
    NONE = "none"


STYLE_INSTRUCTIONS: dict[OpeningStyle, str] = {
    OpeningStyle.ARTIST_LEAD: "Start with the artist's name.",
    OpeningStyle.MOOD_LEAD: "Start by describing how the song feels.",
    OpeningStyle.PREVIOUS_TRACK: "Start by connecting it to the song that just played.",
    OpeningStyle.LISTENER: (
        "Start by talking to the listeners, without assuming where they are or what they are doing."
    ),
    OpeningStyle.DIRECT: "Start by simply saying what is coming up next.",
    OpeningStyle.TIME_OF_DAY: "Start by mentioning the day and the time of day.",
}

PLACEMENT_INSTRUCTIONS: dict[TitlePlacement, str] = {
    TitlePlacement.START: "Say the song title in your first sentence.",
    TitlePlacement.END: "Say the song title at the very end.",
    TitlePlacement.NONE: "Do not say the song title. Name only the artist.",
}


@dataclass(frozen=True)
class Opening:
    style: OpeningStyle
    placement: TitlePlacement


def track_has_mood(track: Track) -> bool:
    """True when the catalog gives the song's valence and arousal."""
    return track.valence is not None and track.arousal is not None


def choose_opening(
    rng: random.Random,
    last_style: OpeningStyle | None = None,
    has_previous: bool = False,
    has_mood: bool = False,
) -> Opening:
    """Pick the opening at random. Every allowed choice is equally likely.

    Not allowed: the same style twice in a row; connecting to a previous song that is not
    given; describing a feeling without valence/arousal (the LLM would invent it); a direct
    intro without the title (there would be almost nothing left to say).
    """
    styles = [
        style
        for style in OpeningStyle
        if style != last_style
        and (has_previous or style != OpeningStyle.PREVIOUS_TRACK)
        and (has_mood or style != OpeningStyle.MOOD_LEAD)
    ]
    style = rng.choice(styles)
    placements = [
        placement
        for placement in TitlePlacement
        if not (style == OpeningStyle.DIRECT and placement == TitlePlacement.NONE)
    ]
    return Opening(style, rng.choice(placements))


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
    opening: Opening | None = None,
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

    if opening is not None:
        lines.append(f"Opening style: {STYLE_INSTRUCTIONS[opening.style]}")
        lines.append(f"Song title placement: {PLACEMENT_INSTRUCTIONS[opening.placement]}")

    lines.append(f"Maximum words: {max_words}")

    lines.extend(recent_lines(recent_announcements))

    return "\n".join(lines)


def generate_song_intro(
    llm: LLMClient,
    next_track: Track,
    previous_track: Track | None = None,
    recent_announcements: Sequence[str] = (),
    opening: Opening | None = None,
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> AnnouncementSpec:
    """Write a song intro with the LLM. Never raises: falls back to a template.

    ``now`` and ``rng`` can be given so tests get the same result every run.
    """
    rng = rng or random.Random()
    now = now or datetime.now(DEFAULT_TIMEZONE)
    # The planner replays the same song when the music source is down: not a real previous.
    has_previous = previous_track is not None and previous_track.id != next_track.id
    opening = opening or choose_opening(
        rng, has_previous=has_previous, has_mood=track_has_mood(next_track)
    )

    max_words = rng.randint(MIN_WORDS, MAX_WORDS)
    # Only the style that needs it gets the extra information. Given every time, the LLM used
    # it every time ("Tuesday afternoon" in 8 of 10 intros in #72).
    give_previous = opening.style == OpeningStyle.PREVIOUS_TRACK
    give_day_part = opening.style == OpeningStyle.TIME_OF_DAY

    prompt = build_song_intro_prompt(
        next_track,
        max_words,
        previous_track=previous_track if give_previous else None,
        day_part=describe_day_part(now) if give_day_part else None,
        recent_announcements=recent_announcements,
        opening=opening,
    )
    system = load_prompt("song_intro")

    spec = ask_llm_for_spec(llm, prompt, system, AnnouncementKind.SONG_INTRO)
    return spec or fallback_song_intro(next_track)
