import random
from datetime import datetime
from zoneinfo import ZoneInfo

from app.content.dj.song_intro import (
    MOOD_TEMPLATES,
    Opening,
    OpeningStyle,
    TitlePlacement,
    build_song_intro_prompt,
    choose_opening,
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


def test_fallback_follows_the_song_mood():
    happy = fallback_song_intro(make_track(valence=0.85, arousal=0.5))
    sad = fallback_song_intro(make_track(valence=0.15, arousal=0.2))
    lively = fallback_song_intro(make_track(valence=0.8, arousal=0.9))

    assert happy.emotion == Emotion.HAPPY
    assert sad.emotion == Emotion.SAD
    assert lively.emotion == Emotion.EXCITED
    for spec in (happy, sad, lively):
        assert "Rain" in spec.text and "Ava" in spec.text


def test_fallback_is_the_same_for_the_same_song():
    track = make_track(valence=0.15, arousal=0.6)
    assert fallback_song_intro(track) == fallback_song_intro(track)
    assert fallback_song_intro(track).emotion == Emotion.SERIOUS


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
    """Fixed "random" choices: the word limit, and always the first allowed option."""

    def __init__(self, words=20):
        self.words = words

    def randint(self, low, high):
        return self.words

    def choice(self, options):
        return options[0]


def generate(llm, **kwargs):
    return generate_song_intro(
        llm,
        make_track(),
        now=FRIDAY_EVENING,
        rng=FakeRandom(),
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


PREVIOUS = make_track(title="Sun", artist="Leo", track_id="trk_prev")


def test_previous_song_is_given_only_for_its_style():
    llm = FakeLLM(GOOD_ANSWER)
    opening = Opening(OpeningStyle.PREVIOUS_TRACK, TitlePlacement.END)
    generate(llm, previous_track=PREVIOUS, opening=opening)
    assert 'Song that just played: "Sun" by Leo' in llm.calls[0]
    assert "Day and time of day" not in llm.calls[0]


def test_day_part_is_given_only_for_its_style():
    llm = FakeLLM(GOOD_ANSWER)
    opening = Opening(OpeningStyle.TIME_OF_DAY, TitlePlacement.END)
    generate(llm, previous_track=PREVIOUS, opening=opening)
    assert "Day and time of day: Friday evening" in llm.calls[0]
    assert "just played" not in llm.calls[0]


def test_other_styles_get_neither():
    llm = FakeLLM(GOOD_ANSWER)
    opening = Opening(OpeningStyle.ARTIST_LEAD, TitlePlacement.END)
    generate(llm, previous_track=PREVIOUS, opening=opening)
    assert "Day and time of day" not in llm.calls[0]
    assert "just played" not in llm.calls[0]


def test_opening_lines_go_into_the_prompt():
    llm = FakeLLM(GOOD_ANSWER)
    generate(llm, opening=Opening(OpeningStyle.ARTIST_LEAD, TitlePlacement.NONE))
    assert "Opening style: Start with the artist's name." in llm.calls[0]
    placement = "Song title placement: Do not say the song title. Name only the artist."
    assert placement in llm.calls[0]
    assert "Maximum words: 20" in llm.calls[0]


def test_an_opening_is_chosen_when_none_is_given():
    llm = FakeLLM(GOOD_ANSWER)
    generate(llm)
    assert "Opening style:" in llm.calls[0]


def choose_many(times=600, **kwargs):
    return [choose_opening(random.Random(seed), **kwargs) for seed in range(times)]


def test_every_style_and_placement_is_chosen_about_equally():
    openings = choose_many(has_previous=True, has_mood=True)
    for style in OpeningStyle:
        assert 60 < sum(o.style == style for o in openings) < 140  # ~100 each
    assert {o.placement for o in openings} == set(TitlePlacement)


def test_the_last_style_is_not_repeated():
    for style in OpeningStyle:
        openings = choose_many(last_style=style, has_previous=True, has_mood=True)
        assert all(o.style != style for o in openings)


def test_previous_track_style_needs_a_previous_song():
    openings = choose_many(has_mood=True)
    assert all(o.style != OpeningStyle.PREVIOUS_TRACK for o in openings)


def test_mood_style_needs_valence_and_arousal():
    openings = choose_many(has_previous=True)
    assert all(o.style != OpeningStyle.MOOD_LEAD for o in openings)


def test_direct_style_always_says_the_title():
    openings = choose_many(has_previous=True, has_mood=True)
    direct = [o for o in openings if o.style == OpeningStyle.DIRECT]
    assert direct
    assert all(o.placement != TitlePlacement.NONE for o in direct)


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


BANNED_PHRASES = ("slow things down", "sit back", "wash over you")


def test_fallback_templates_follow_the_dj_rules():
    for templates in MOOD_TEMPLATES.values():
        for template in templates:
            lowered = template.lower()
            assert not any(phrase in lowered for phrase in BANNED_PHRASES), template
            assert "tonight" not in lowered, template
