import asyncio
import random
from contextlib import contextmanager

import pytest

from app.contracts import Emotion, Track
from app.music.selection import NoTrackAvailable, TrackSelector, choose_track
from app.music.source import CatalogMusicSource


def make_track(n: int) -> Track:
    return Track(
        id=f"t{n}",
        title=f"Song {n}",
        artist=f"Artist {n}",
        duration_seconds=100.0 + n,
        license="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        source_url=f"https://example.org/{n}",
    )


CATALOG = [make_track(n) for n in range(1, 4)]


class FakeSelector(TrackSelector):
    """Uses the real repeat rules on an in-memory catalog."""

    def __init__(self, catalog: list[Track]) -> None:
        self.catalog = catalog
        self.seen_history: list[Track] = []

    def next_track(self, history, emotion: Emotion | None = None) -> Track:
        self.seen_history = list(history)
        return choose_track(self.catalog, history, emotion, random.Random(1), recent_limit=10)


def make_source(catalog: list[Track]) -> tuple[CatalogMusicSource, FakeSelector]:
    selector = FakeSelector(catalog)

    @contextmanager
    def session_factory():
        yield object()

    by_id = {t.id: t for t in catalog}
    source = CatalogMusicSource(
        session_factory,
        selector_factory=lambda db: selector,
        history_loader=lambda db, ids: [by_id[i] for i in ids if i in by_id],
    )
    return source, selector


def next_track(source, recent=(), user_id="usr_1"):
    return asyncio.run(source.next_track(user_id=user_id, recent_track_ids=list(recent)))


def test_picks_a_track_and_maps_fields():
    source, _ = make_source([CATALOG[0]])

    info = next_track(source)

    assert info.track_id == "t1"
    assert info.title == "Song 1"
    assert info.artist == "Artist 1"
    assert info.duration_s == 101.0
    assert info.license == "CC BY 4.0"


def test_recent_track_ids_reach_the_selector_and_are_avoided():
    source, selector = make_source(CATALOG)

    for seed_run in range(5):
        info = next_track(source, recent=["t1", "t2"])
        assert info.track_id == "t3", seed_run
    assert [t.id for t in selector.seen_history] == ["t1", "t2"]


def test_empty_profile_and_unknown_user_still_get_a_track():
    source, _ = make_source(CATALOG)

    info = next_track(source, user_id="usr_without_profile")

    assert info.track_id in {"t1", "t2", "t3"}


def test_unknown_recent_ids_are_ignored():
    source, selector = make_source(CATALOG)

    next_track(source, recent=["gone", "t2"])

    assert [t.id for t in selector.seen_history] == ["t2"]


def test_empty_catalog_raises_no_track_available():
    source, _ = make_source([])

    with pytest.raises(NoTrackAvailable, match="catalog is empty"):
        next_track(source)
