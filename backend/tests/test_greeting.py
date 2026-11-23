from datetime import datetime

import pytest

from app.content.dj.greeting import (
    generate_greeting,
    has_placeholders,
    hour_name,
    spoken_time,
)
from app.content.llm import LLMClient, LLMError
from app.contracts import AnnouncementKind, Track


@pytest.mark.parametrize(
    ("hour", "expected"),
    [
        (0, "midnight"),
        (12, "noon"),
        (9, "nine"),
        (21, "nine"),
        (13, "one"),
        (24, "midnight"),
    ],
)
def test_hour_name(hour, expected):
    assert hour_name(hour) == expected


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (9, 0, "nine o'clock"),
        (9, 5, "nine o'clock"),
        (9, 6, "just after nine"),
        (9, 13, "quarter past nine"),
        (9, 23, "half past nine"),
        (9, 37, "half past nine"),
        (9, 38, "quarter to ten"),
        (9, 48, "almost ten"),
        (9, 54, "almost ten"),
        (8, 55, "nine o'clock"),
        (21, 30, "half past nine"),
        (23, 50, "almost midnight"),
        (23, 55, "midnight"),
        (0, 15, "quarter past midnight"),
        (11, 58, "noon"),
    ],
)
def test_spoken_time(hour, minute, expected):
    now = datetime(2026, 11, 23, hour, minute)
    assert spoken_time(now) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Good evening, it's {time} on {station}. Here's Sunrise.", True),
        ("Good evening on {station}. Here's Sunrise.", False),
        ("Good evening, it's {time}. Here's Sunrise.", False),
        ("It's {time}, yes, {time}, on {station}.", False),
    ],
)
def test_has_placeholders(text, expected):
    assert has_placeholders(text) == expected


NOW = datetime(2026, 11, 23, 21, 30)  # a Monday, "half past nine", "Monday night"
STATION = "Bilim Radio"
GOOD_ANSWER = {"emotion": "calm", "text": "Evening, it's {time} on {station}. Here's Rain."}
NO_TIME_ANSWER = {"emotion": "calm", "text": "Evening on {station}. Here's Rain."}


def make_track() -> Track:
    return Track(
        id="trk_test",
        title="Rain",
        artist="Ava",
        duration_seconds=180,
        license="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        source_url="https://example.org/tracks/rain",
    )


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


def greet(llm):
    return generate_greeting(llm, make_track(), STATION, now=NOW)


def test_placeholders_are_filled():
    spec = greet(FakeLLM(GOOD_ANSWER))
    assert spec.text == "Evening, it's half past nine on Bilim Radio. Here's Rain."
    assert spec.kind == AnnouncementKind.GREETING


def test_prompt_gives_the_day_part():
    llm = FakeLLM(GOOD_ANSWER)
    greet(llm)
    assert "Day and time of day: Monday night" in llm.calls[0]


def test_missing_placeholder_is_tried_once_more():
    llm = FakeLLM(NO_TIME_ANSWER, GOOD_ANSWER)
    spec = greet(llm)
    assert len(llm.calls) == 2
    assert "half past nine" in spec.text


def test_missing_placeholder_twice_gives_the_fallback():
    spec = greet(FakeLLM(NO_TIME_ANSWER, NO_TIME_ANSWER))
    assert spec.text == "It's half past nine on Bilim Radio. Up next, Rain by Ava."


def test_llm_error_gives_the_fallback():
    spec = greet(FakeLLM(LLMError("down")))
    assert spec.text.startswith("It's half past nine on Bilim Radio.")
