from app.content.dj.song_intro import fallback_song_intro
from app.contracts import AnnouncementKind, Emotion, Track


def make_track(title: str = "Rain", artist: str = "Ava") -> Track:
    return Track(
        id="trk_test",
        title=title,
        artist=artist,
        duration_seconds=180,
        license="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        source_url="https://example.org/tracks/rain",
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
