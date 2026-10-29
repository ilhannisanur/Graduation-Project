from app.content.dj.song_intro import build_song_intro_prompt, fallback_song_intro
from app.contracts import AnnouncementKind, Emotion, Track


def make_track(
    title: str = "Rain",
    artist: str = "Ava",
    track_id: str = "trk_test",
    valence: float | None = None,
    arousal: float | None = None,
) -> Track:
    return Track(
        id=track_id,
        title=title,
        artist=artist,
        duration_seconds=180,
        license="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        source_url="https://example.org/tracks/rain",
        valence=valence,
        arousal=arousal,
    )


def test_text_mentions_title_and_artist():
    spec = fallback_song_intro(make_track())
    assert spec.text == "Up next, Rain by Ava."


def test_short_text_uses_minimum_seconds():
    spec = fallback_song_intro(make_track())
    assert spec.target_seconds == 3.0


def test_kind_and_emotion():
    spec = fallback_song_intro(make_track())
    assert spec.kind == AnnouncementKind.SONG_INTRO
    assert spec.emotion == Emotion.NEUTRAL


# --- build_song_intro_prompt ---------------------------------------------------


def test_prompt_with_only_required_fields():
    prompt = build_song_intro_prompt(make_track(), max_words=25)
    assert prompt == 'Next song: "Rain" by Ava\nMaximum words: 25'


def test_prompt_with_all_fields():
    prompt = build_song_intro_prompt(
        make_track(valence=0.62, arousal=0.25),
        max_words=25,
        previous_track=make_track(title="Sun", artist="Leo", track_id="trk_prev"),
        day_part="Friday evening",
        recent_announcements=["First one.", "Second one."],
    )
    assert prompt.splitlines() == [
        'Next song: "Rain" by Ava',
        "Valence: 0.62, arousal: 0.25",
        'Song that just played: "Sun" by Leo',
        "Day and time of day: Friday evening",
        "Maximum words: 25",
        "Your most recent announcements:",
        "1. First one.",
        "2. Second one.",
    ]


def test_no_valence_line_when_one_value_is_missing():
    prompt = build_song_intro_prompt(make_track(valence=0.62), max_words=25)
    assert "Valence" not in prompt


def test_zero_valence_and_arousal_are_written():
    prompt = build_song_intro_prompt(make_track(valence=0.0, arousal=0.0), max_words=25)
    assert "Valence: 0.00, arousal: 0.00" in prompt


def test_no_previous_song_line_when_the_same_song_repeats():
    prompt = build_song_intro_prompt(make_track(), max_words=25, previous_track=make_track())
    assert "just played" not in prompt


def test_no_day_line_when_day_part_is_empty():
    prompt = build_song_intro_prompt(make_track(), max_words=25, day_part="")
    assert "Day and time of day" not in prompt
