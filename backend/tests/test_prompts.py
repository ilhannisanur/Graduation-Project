import pytest

from app.content.dj.prompts import load_prompt
from app.contracts import Emotion


def test_song_intro_prompt_loads():
    text = load_prompt("song_intro")
    assert text.strip() != ""


def test_song_intro_prompt_lists_every_emotion():
    text = load_prompt("song_intro")
    lines = [line for line in text.splitlines() if "Choose exactly one of:" in line]
    assert len(lines) == 1
    for emotion in Emotion:
        assert emotion.value in lines[0]


def test_missing_prompt_raises():
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist")
