import asyncio
from contextlib import contextmanager

from app.content.director import SongIntroDirector
from app.content.llm import LLMClient, LLMError
from app.contracts import Track
from app.radio.planner.models import AnnouncementRequest, TrackInfo


def make_track(n: int, valence: float | None = None, arousal: float | None = None) -> Track:
    return Track(
        id=f"t{n}",
        title=f"Song {n}",
        artist=f"Artist {n}",
        duration_seconds=180,
        license="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        source_url=f"https://example.org/{n}",
        valence=valence,
        arousal=arousal,
    )


def info(track: Track) -> TrackInfo:
    return TrackInfo(track_id=track.id, title=track.title, artist=track.artist, duration_s=180)


class FakeLLM(LLMClient):
    def __init__(self, answer):
        self.answer = answer
        self.prompts = []

    def generate_text(self, prompt, system=None):
        raise NotImplementedError

    def generate_json(self, prompt, system=None):
        self.prompts.append(prompt)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


GOOD_ANSWER = {"emotion": "calm", "text": "Here's Song 1 by Artist 1, nice and easy."}


def make_director(llm, catalog):
    loaded_ids = []

    @contextmanager
    def session_factory():
        yield object()

    def track_loader(db, ids):
        loaded_ids.extend(ids)
        by_id = {t.id: t for t in catalog}
        return [by_id[i] for i in ids if i in by_id]

    director = SongIntroDirector(llm, session_factory, track_loader=track_loader)
    return director, loaded_ids


def plan(director, next_track, previous_track=None):
    request = AnnouncementRequest(
        previous_track=info(previous_track) if previous_track else None,
        next_track=info(next_track),
    )
    return asyncio.run(director.plan(request))


def test_plan_carries_text_emotion_and_duration():
    song = make_track(1)
    director, _ = make_director(FakeLLM(GOOD_ANSWER), [song])
    result = plan(director, song)
    assert result.text == GOOD_ANSWER["text"]
    assert result.emotion == "calm"
    assert result.target_duration_s == 3.6  # 9 words / 2.5 words per second


def test_catalog_track_is_used_for_valence_and_arousal():
    song = make_track(1, valence=0.7, arousal=0.2)
    llm = FakeLLM(GOOD_ANSWER)
    director, _ = make_director(llm, [song])
    plan(director, song)
    assert "Valence: 0.70, arousal: 0.20" in llm.prompts[0]


def test_both_songs_are_loaded_from_the_catalog():
    previous, song = make_track(1), make_track(2)
    director, loaded_ids = make_director(FakeLLM(GOOD_ANSWER), [previous, song])
    plan(director, song, previous)
    assert loaded_ids == ["t2", "t1"]


def test_song_missing_from_catalog_still_gets_an_intro():
    song = make_track(9)
    llm = FakeLLM(GOOD_ANSWER)
    director, _ = make_director(llm, [])
    result = plan(director, song)
    assert 'Next song: "Song 9" by Artist 9' in llm.prompts[0]
    assert result.text == GOOD_ANSWER["text"]


def test_llm_error_gives_the_template_intro():
    song = make_track(1)
    director, _ = make_director(FakeLLM(LLMError("down")), [song])
    result = plan(director, song)
    assert result.text == "Up next, Song 1 by Artist 1."
    assert result.emotion == "neutral"
