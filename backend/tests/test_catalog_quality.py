"""Catalog quality (#107): popularity, sung songs, removing dull instrumentals."""

import json
import random
from collections import Counter

import httpx
import pytest
from sqlalchemy import select

from app.contracts import Track
from app.music import TrackRow, curate
from app.music import download as dl
from app.music.mood_target import PRESETS, RECENT_LIMIT, choose_for_target
from app.music.selection import choose_track
from app.music.selection.quality import (
    RECENT_ONE_HOUR,
    TrackQuality,
    needs_vocals,
    popularity_from_listens,
)


def track(n: int, valence: float = 0.6, energy: float = 0.1) -> Track:
    return Track(
        id=f"t{n}",
        title=f"Song {n}",
        artist=f"Artist {n}",
        duration_seconds=200,
        license="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        source_url="https://example.org",
        mood_tags=["calm"],
        valence=valence,
        arousal=energy,
    )


# ---------------------------------------------------------------- popularity


@pytest.mark.parametrize(
    ("listens", "low", "high"),
    [(0, 0.0, 0.0), (1000, 0.45, 0.5), (100_000, 0.78, 0.82), (2_000_000, 1.0, 1.0)],
)
def test_popularity_grows_with_listens_on_a_log_scale(listens, low, high):
    assert low <= popularity_from_listens(listens) <= high


def test_popularity_of_an_unknown_count_is_unknown():
    assert popularity_from_listens(None) is None
    assert popularity_from_listens(50_000_000) == 1.0


def test_popular_songs_are_picked_more_often_but_not_always():
    calm = PRESETS["calm"]
    songs = [track(1), track(2)]
    qualities = {"t1": TrackQuality(popularity=1.0), "t2": TrackQuality(popularity=0.0)}

    picks = Counter(
        choose_for_target(songs, [], calm, random.Random(seed), qualities).id for seed in range(400)
    )

    assert picks["t1"] > 1.8 * picks["t2"]  # about 2.5x
    assert picks["t2"] > 50  # the less popular one still plays


# ---------------------------------------------------------------- sung songs


def test_two_instrumentals_in_a_row_ask_for_a_sung_song():
    instrumental = TrackQuality(has_vocals=False)
    sung = TrackQuality(has_vocals=True)
    qualities = {"a": instrumental, "b": instrumental, "c": sung}

    assert needs_vocals(["a", "b"], qualities)
    assert not needs_vocals(["c", "b"], qualities)
    assert not needs_vocals(["b"], qualities)
    assert not needs_vocals(["a", "unknown"], qualities)


def test_target_picks_a_sung_song_after_two_instrumentals():
    calm = PRESETS["calm"]
    played = [track(1), track(2)]
    options = [track(3), track(4), track(5)]
    qualities = {
        "t1": TrackQuality(has_vocals=False),
        "t2": TrackQuality(has_vocals=False),
        "t3": TrackQuality(has_vocals=False),
        "t4": TrackQuality(has_vocals=True),
        "t5": TrackQuality(has_vocals=False),
    }

    for seed in range(30):
        picked = choose_for_target(
            played + options, ["t1", "t2"], calm, random.Random(seed), qualities
        )
        assert picked.id == "t4"


def test_only_instrumentals_left_still_play():
    calm = PRESETS["calm"]
    qualities = {f"t{i}": TrackQuality(has_vocals=False) for i in range(1, 4)}

    picked = choose_for_target(
        [track(1), track(2), track(3)], ["t1", "t2"], calm, random.Random(0), qualities
    )

    assert picked.id == "t3"


def test_random_source_also_prefers_a_sung_song():
    songs = [track(i) for i in range(1, 6)]
    qualities = {t.id: TrackQuality(has_vocals=False) for t in songs}
    qualities["t5"] = TrackQuality(has_vocals=True)

    for seed in range(20):
        picked = choose_track(songs, songs[:2], None, random.Random(seed), qualities=qualities)
        assert picked.id == "t5"


# ------------------------------------------------------------------- repeats


def test_a_song_does_not_come_back_within_an_hour():
    calm = PRESETS["calm"]
    songs = [track(i) for i in range(RECENT_ONE_HOUR + 1)]
    played = [s.id for s in songs[:RECENT_ONE_HOUR]]

    assert RECENT_LIMIT == RECENT_ONE_HOUR
    for seed in range(20):
        picked = choose_for_target(songs, played, calm, random.Random(seed))
        assert picked.id == songs[-1].id


# ------------------------------------------------------------- the download


def mtg(*ids: int) -> list[dl.MtgTrack]:
    return [dl.MtgTrack(i, ("happy",)) for i in ids]


def test_popular_candidates_keep_popularity_order_and_need_mood_tags():
    chosen = dl.popular_candidates(mtg(1, 2, 3), [3, 99, 1, 3])

    assert [c.jamendo_id for c in chosen] == [3, 1]


def test_listening_info_reads_stats_and_music_info():
    item = {
        "stats": {"rate_listened_total": 12345},
        "musicinfo": {"vocalinstrumental": "vocal", "tags": {"genres": ["pop", "rock"]}},
    }

    assert dl.listening_info(item) == {
        "listens": 12345,
        "has_vocals": True,
        "genres": ["pop", "rock"],
    }
    assert dl.listening_info({}) == {"listens": None, "has_vocals": None, "genres": []}


class PopularJamendo:
    """The popular list and per-track answers of the Jamendo API."""

    def __init__(self, popular: list[int], items: dict[int, dict]):
        self.popular = popular
        self.items = items

    def handler(self, request: httpx.Request) -> httpx.Response:
        params = request.url.params
        if "order" in params:
            offset, limit = int(params["offset"]), int(params["limit"])
            results = [{"id": str(i)} for i in self.popular[offset : offset + limit]]
        elif request.url.host == "api.jamendo.com":
            ids = [int(i) for i in params["id"].split()]
            results = [self.items[i] for i in ids if i in self.items]
        else:
            return httpx.Response(200, content=b"ID3" + b"x" * 100)
        return httpx.Response(200, json={"headers": {"status": "success"}, "results": results})

    def client(self) -> dl.JamendoClient:
        http = httpx.Client(transport=httpx.MockTransport(self.handler))
        return dl.JamendoClient(http, "SECRETKEY", sleep=lambda _s: None)


def api_item(track_id: int, listens: int, kind: str) -> dict:
    return {
        "id": str(track_id),
        "name": f"Song {track_id}",
        "duration": 200,
        "artist_name": "Some Artist",
        "license_ccurl": "http://creativecommons.org/licenses/by-sa/3.0/",
        "shareurl": f"https://www.jamendo.com/track/{track_id}",
        "audiodownload": f"https://dl.example.org/{track_id}/",
        "audiodownload_allowed": True,
        "licenses": {"ccnd": "false"},
        "stats": {"rate_listened_total": listens},
        "musicinfo": {"vocalinstrumental": kind, "tags": {"genres": ["pop"]}},
    }


def test_popular_list_is_read_page_by_page():
    fake = PopularJamendo(list(range(1, 451)), {})

    assert fake.client().popular_ids("vocal", 450) == list(range(1, 451))


def test_download_stores_listening_info_and_skips_removed_tracks(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({"version": 1, "tracks": [], "removed": {"2": "dull"}}), encoding="utf-8"
    )
    fake = PopularJamendo(
        [], {1: api_item(1, 900_000, "vocal"), 2: api_item(2, 10, "instrumental")}
    )

    dl.run(fake.client(), tmp_path, mtg(1, 2), target=10, dry_run=False, out=lambda _m: None)

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert [e["source_track_id"] for e in manifest["tracks"]] == ["1"]
    assert manifest["tracks"][0]["listens"] == 900_000
    assert manifest["tracks"][0]["has_vocals"] is True
    assert manifest["removed"] == {"2": "dull"}


# ------------------------------------------------------------------- pruning


def entry(source_id: str, listens: int | None, has_vocals: bool | None) -> dict:
    return {
        "source": "jamendo",
        "source_track_id": source_id,
        "title": f"Song {source_id}",
        "artist": "Some Artist",
        "duration_seconds": 200.0,
        "license": "CC BY 3.0",
        "license_url": "http://creativecommons.org/licenses/by/3.0/",
        "source_url": f"https://www.jamendo.com/track/{source_id}",
        "mood_tags": ["calm"],
        "file": f"{source_id}.mp3",
        "listens": listens,
        "has_vocals": has_vocals,
        "genres": [],
    }


def test_only_little_listened_tracks_are_pruned():
    entries = {
        "1": entry("1", 100, False),  # little-listened instrumental: goes
        "2": entry("2", 9_999, True),  # little-listened sung song: goes
        "3": entry("3", 10_000, False),  # at the limit: stays
        "4": entry("4", 90_000, True),  # popular: stays
        "5": entry("5", None, False),  # unknown listens: stays
    }

    assert [e["source_track_id"] for e in curate.prune_candidates(entries)] == ["1", "2"]


def write_catalog(music_dir, entries):
    (music_dir / "audio").mkdir()
    for e in entries:
        (music_dir / "audio" / e["file"]).write_bytes(b"ID3")
    dl.save_manifest(music_dir / "manifest.json", {e["source_track_id"]: e for e in entries}, {})


def test_prune_dry_run_changes_nothing(tmp_path):
    write_catalog(tmp_path, [entry("1", 100, False), entry("2", 500_000, True)])

    chosen = curate.prune(None, tmp_path, out=lambda _m: None)

    assert [e["source_track_id"] for e in chosen] == ["1"]
    assert (tmp_path / "audio" / "1.mp3").exists()
    assert set(dl.load_manifest(tmp_path / "manifest.json")) == {"1", "2"}


def test_prune_removes_file_manifest_entry_and_database_row(tmp_path, db_session):
    dull, sung = entry("9100001", 100, False), entry("9100002", 500_000, True)
    write_catalog(tmp_path, [dull, sung])
    for e in (dull, sung):
        db_session.add(
            TrackRow(
                source="jamendo",
                source_track_id=e["source_track_id"],
                title=e["title"],
                artist=e["artist"],
                duration_seconds=e["duration_seconds"],
                license=e["license"],
                license_url=e["license_url"],
                source_url=e["source_url"],
            )
        )
    db_session.flush()

    curate.prune(db_session, tmp_path, out=lambda _m: None)
    db_session.flush()

    assert not (tmp_path / "audio" / "9100001.mp3").exists()
    assert set(dl.load_manifest(tmp_path / "manifest.json")) == {"9100002"}
    assert dl.load_removed(tmp_path / "manifest.json") == {"9100001": curate.PRUNE_REASON}
    left = db_session.scalars(
        select(TrackRow.source_track_id).where(TrackRow.source_track_id.in_(["9100001", "9100002"]))
    ).all()
    assert left == ["9100002"]


def test_enrich_fills_the_manifest(tmp_path):
    write_catalog(tmp_path, [entry("1", None, None), entry("2", None, None)])
    fake = PopularJamendo([], {1: api_item(1, 4321, "instrumental")})  # 2 gets no answer

    filled = curate.enrich(fake.client(), tmp_path, out=lambda _m: None)

    entries = dl.load_manifest(tmp_path / "manifest.json")
    assert filled == 1
    assert entries["1"]["listens"] == 4321
    assert entries["1"]["has_vocals"] is False
    assert entries["2"]["listens"] is None
