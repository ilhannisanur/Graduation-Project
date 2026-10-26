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
