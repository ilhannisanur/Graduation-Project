from datetime import datetime

HOUR_WORDS = [
    "twelve",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
]


ON_THE_HOUR = "{} o'clock"

# (the minute is below this number, phrase, hours to add)
TIME_PHRASES = [
    (6, ON_THE_HOUR, 0),
    (13, "just after {}", 0),
    (23, "quarter past {}", 0),
    (38, "half past {}", 0),
    (48, "quarter to {}", 1),
    (55, "almost {}", 1),
    (60, ON_THE_HOUR, 1),
]


def hour_name(hour: int) -> str:
    """Say an hour (0-24) the way a DJ would: 'nine', 'midnight', 'noon'."""
    hour = hour % 24
    if hour == 0:
        return "midnight"
    if hour == 12:
        return "noon"
    return HOUR_WORDS[hour % 12]


def spoken_time(now: datetime) -> str:
    """Say the time the way a DJ would, for example 'half past nine'."""
    for end_minute, phrase, hour_offset in TIME_PHRASES:
        if now.minute < end_minute:
            name = hour_name(now.hour + hour_offset)
            if phrase == ON_THE_HOUR and name in ("midnight", "noon"):
                return name
            return phrase.format(name)
