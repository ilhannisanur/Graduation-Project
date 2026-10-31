from datetime import datetime
from zoneinfo import ZoneInfo

from app.content.dj.song_intro import (
    build_song_intro_prompt,
    describe_day_part,
    fallback_song_intro,
    generate_song_intro,
)
from app.content.llm import LLMClient, LLMError
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


# --- generate_song_intro -------------------------------------------------------

ISTANBUL = ZoneInfo("Europe/Istanbul")
FRIDAY_EVENING = datetime(2026, 10, 30, 19, 0, tzinfo=ISTANBUL)
GOOD_ANSWER = {"emotion": "happy", "text": "Here's Rain by Ava, enjoy it."}


class FakeLLM(LLMClient):
    """Returns the given answers in order; an exception in the list is raised."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def generate_text(self, prompt, system=None):
        raise NotImplementedError

    def generate_json(self, prompt, system=None):
        self.calls.append(prompt)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeRandom:
    """Fixed "random" choices: the word limit and whether extras are given."""

    def __init__(self, words=20, give_extras=True):
        self.words = words
        self.value = 0.0 if give_extras else 0.99

    def randint(self, low, high):
        return self.words

    def random(self):
        return self.value


def generate(llm, give_extras=True, **kwargs):
    return generate_song_intro(
        llm,
        make_track(),
        now=FRIDAY_EVENING,
        rng=FakeRandom(give_extras=give_extras),
        **kwargs,
    )


def test_valid_answer_becomes_announcement():
    spec = generate(FakeLLM(GOOD_ANSWER))
    assert spec.kind == AnnouncementKind.SONG_INTRO
    assert spec.text == GOOD_ANSWER["text"]
    assert spec.emotion == Emotion.HAPPY
    assert spec.target_seconds == 3.0  # 6 words / 2.5 is below the minimum


def test_invalid_emotion_is_retried_once():
    llm = FakeLLM({"emotion": "angry", "text": "Hi."}, GOOD_ANSWER)
    spec = generate(llm)
    assert len(llm.calls) == 2
    assert spec.emotion == Emotion.HAPPY


def test_empty_text_is_retried_once():
    llm = FakeLLM({"emotion": "happy", "text": "  "}, GOOD_ANSWER)
    spec = generate(llm)
    assert len(llm.calls) == 2
    assert spec.text == GOOD_ANSWER["text"]


def test_two_bad_answers_give_fallback():
    llm = FakeLLM({"emotion": "angry", "text": "Hi."}, {"text": "No emotion."})
    spec = generate(llm)
    assert len(llm.calls) == 2
    assert spec == fallback_song_intro(make_track())


def test_llm_error_gives_fallback_without_retry():
    llm = FakeLLM(LLMError("timeout"), GOOD_ANSWER)
    spec = generate(llm)
    assert len(llm.calls) == 1
    assert spec == fallback_song_intro(make_track())


def test_extras_are_given_when_chosen():
    llm = FakeLLM(GOOD_ANSWER)
    previous = make_track(title="Sun", artist="Leo", track_id="trk_prev")
    generate(llm, previous_track=previous, give_extras=True)
    assert "Maximum words: 20" in llm.calls[0]
    assert "Day and time of day: Friday evening" in llm.calls[0]
    assert 'Song that just played: "Sun" by Leo' in llm.calls[0]


def test_extras_are_left_out_when_not_chosen():
    llm = FakeLLM(GOOD_ANSWER)
    previous = make_track(title="Sun", artist="Leo", track_id="trk_prev")
    generate(llm, previous_track=previous, give_extras=False)
    assert "Day and time of day" not in llm.calls[0]
    assert "just played" not in llm.calls[0]


def test_day_parts():
    def at(hour):
        return describe_day_part(datetime(2026, 10, 30, hour, 0, tzinfo=ISTANBUL))

    assert at(8) == "Friday morning"
    assert at(13) == "Friday afternoon"
    assert at(19) == "Friday evening"
    assert at(23) == "Friday night"
    assert at(2) == "Friday night"


def test_emotion_case_and_spaces_are_accepted():
    spec = generate(FakeLLM({"emotion": " Happy", "text": "Here's Rain."}))
    assert spec.emotion == Emotion.HAPPY
