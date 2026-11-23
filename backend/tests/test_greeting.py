from datetime import datetime

import pytest

from app.content.dj.greeting import hour_name, spoken_time


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
