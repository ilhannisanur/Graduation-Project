from collections.abc import Sequence

from app.contracts import AnnouncementKind, AnnouncementSpec, Emotion, Track

WORDS_PER_SECOND = 2.5
MIN_SECONDS = 3.0


def fallback_song_intro(track: Track) -> AnnouncementSpec:
    """Template announcement used when the LLM fails or times out."""
    text = f"Up next, {track.title} by {track.artist}."
    word_count = len(text.split())
    seconds = max(MIN_SECONDS, word_count / WORDS_PER_SECOND)

    return AnnouncementSpec(
        kind=AnnouncementKind.SONG_INTRO,
        text=text,
        emotion=Emotion.NEUTRAL,
        target_seconds=seconds,
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
