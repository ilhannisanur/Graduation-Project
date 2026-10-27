import random

import pytest
from sqlalchemy.orm import Session

from app.contracts import Emotion, Track
from app.music import TrackRow
from app.music.selection import (
    EMOTION_TAGS,
    NoTrackAvailable,
    RandomSelector,
    TrackSelector,
    choose_track,
)


def track(n: int, artist: str | None = None, tags: tuple[str, ...] = ()) -> Track:
    return Track(
        id=f"t{n}",
        title=f"Song {n}",
        artist=artist or f"Artist {n}",
        duration_seconds=100.0,
        license="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        source_url=f"https://example.org/{n}",
        mood_tags=list(tags),
    )


def pick(candidates, history=(), emotion=None, seed=1, recent_limit=10) -> Track:
    return choose_track(candidates, list(history), emotion, random.Random(seed), recent_limit)


def test_every_emotion_has_a_tag_rule():
    assert set(EMOTION_TAGS) == set(Emotion)


def test_picks_only_tracks_that_fit_the_mood():
    candidates = [track(1, tags=("sad",)), track(2, tags=("happy",)), track(3, tags=("calm",))]

    for seed in range(20):
        assert pick(candidates, emotion=Emotion.HAPPY, seed=seed).id == "t2"


def test_neutral_and_unknown_emotion_mean_no_filter():
    candidates = [track(1, tags=("sad",)), track(2, tags=("happy",))]

    ids = {pick(candidates, emotion=Emotion.NEUTRAL, seed=s).id for s in range(30)}
    ids |= {pick(candidates, emotion=None, seed=s).id for s in range(30)}

    assert ids == {"t1", "t2"}


def test_recent_songs_are_not_repeated():
    candidates = [track(n) for n in range(5)]
    history = candidates[:4]

    for seed in range(20):
        assert pick(candidates, history, seed=seed).id == "t4"


def test_only_the_last_n_songs_are_blocked():
    candidates = [track(n) for n in range(3)]
    history = [candidates[0], candidates[1], candidates[2]]

    ids = {pick(candidates, history, seed=s, recent_limit=1).id for s in range(30)}

    assert ids == {"t0", "t1"}  # t2 was just played; t0 and t1 are old enough


def test_same_artist_does_not_follow_itself():
    candidates = [track(1, artist="A"), track(2, artist="A"), track(3, artist="B")]

    for seed in range(20):
        assert pick(candidates, [track(9, artist="A")], seed=seed).id == "t3"


def test_repeat_rules_win_over_mood_when_nothing_else_is_left():
    # The only happy song was just played, so a mood match would be a repeat: pick the other.
    happy = track(1, tags=("happy",))
    other = track(2, tags=("sad",))

    assert pick([happy, other], [happy], emotion=Emotion.HAPPY).id == "t2"


def test_relaxes_rules_instead_of_going_silent():
    only = track(1, artist="A", tags=("sad",))

    assert pick([only], [only], emotion=Emotion.HAPPY).id == "t1"


def test_same_seed_gives_same_choice():
    candidates = [track(n) for n in range(20)]

    assert pick(candidates, seed=7).id == pick(candidates, seed=7).id


def test_empty_catalog_raises():
    with pytest.raises(NoTrackAvailable):
        pick([])


def add_row(db: Session, n: int, tags: list[str], file_path: str | None = "audio/x.mp3") -> None:
    db.add(
        TrackRow(
            id=f"trk_sel_{n}",
            title=f"Song {n}",
            artist=f"Artist {n}",
            duration_seconds=100.0,
            license="CC BY 4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            source_url=f"https://example.org/{n}",
            mood_tags=tags,
            file_path=file_path,
            source="test-selection",
            source_track_id=str(n),
        )
    )


def test_random_selector_reads_the_database(db_session: Session):
    selector = RandomSelector(db_session, rng=random.Random(3))
    assert isinstance(selector, TrackSelector)
    # The real catalog may be in the database too; any serious-fitting track is a valid answer.
    add_row(db_session, 1, ["documentary"])
    db_session.flush()

    result = selector.next_track([], Emotion.SERIOUS)

    assert isinstance(result, Track)
    assert set(result.mood_tags) & set(EMOTION_TAGS[Emotion.SERIOUS])


def test_random_selector_skips_tracks_without_audio(db_session: Session):
    add_row(db_session, 2, ["calm"], file_path=None)
    db_session.flush()
    selector = RandomSelector(db_session, rng=random.Random(5))

    ids = {selector.next_track([], Emotion.CALM).id for _ in range(50)}

    assert "trk_sel_2" not in ids
