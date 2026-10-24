import json
from pathlib import Path

import httpx
import pytest

from app.music import download as dl

# Real MTG layout: tags are tab-separated columns after DURATION, with a prefix, CRLF line ends.
TSV_HEADER = "TRACK_ID\tARTIST_ID\tALBUM_ID\tPATH\tDURATION\tTAGS\r\n"


def tsv_line(track_id: int, *tags: str) -> str:
    cols = [
        f"track_{track_id:07d}",
        "artist_000087",
        "album_000149",
        f"{track_id % 100}/{track_id}.mp3",
        "212.7",
        *(f"mood/theme---{t}" for t in tags),
    ]
    return "\t".join(cols) + "\r\n"


def make_tracks(per_label: int = 30) -> list[dl.MtgTrack]:
    lines = [TSV_HEADER]
    next_id = 1000
    for label in dl.SELECT_TAGS:
        for _ in range(per_label):
            lines.append(tsv_line(next_id, label, "film"))
            next_id += 1
    return dl.parse_tsv("".join(lines))


def api_item(track_id: int, **overrides) -> dict:
    item = {
        "id": str(track_id),
        "name": f"Song {track_id}",
        "duration": 200,
        "artist_name": "Some Artist",
        "license_ccurl": "http://creativecommons.org/licenses/by-nc-sa/3.0/",
        "shareurl": f"https://www.jamendo.com/track/{track_id}",
        "audiodownload": f"https://dl.example.org/download/track/{track_id}/mp31/",
        "audiodownload_allowed": True,
        "licenses": {"ccnd": "false"},
    }
    return {**item, **overrides}


class FakeJamendo:
    """Stands in for the Jamendo API and the audio host. Counts requests."""

    def __init__(self, items: dict[int, dict] | None = None):
        self.items = items or {}
        self.api_requests: list[httpx.Request] = []
        self.audio_requests: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.jamendo.com":
            self.api_requests.append(request)
            ids = [int(i) for i in request.url.params["id"].split()]
            results = [self.items[i] for i in ids if i in self.items]
            body = {"headers": {"status": "success", "error_message": ""}, "results": results}
            return httpx.Response(200, json=body)
        self.audio_requests.append(str(request.url))
        return httpx.Response(200, content=b"ID3" + b"x" * 100)

    def client(self) -> dl.JamendoClient:
        http = httpx.Client(transport=httpx.MockTransport(self.handler))
        return dl.JamendoClient(http, "SECRETKEY", sleep=lambda _s: None)


# ------------------------------------------------------------------- parsing


def test_parse_tsv_reads_real_tag_format():
    text = TSV_HEADER + tsv_line(948, "background") + tsv_line(5634, "documentary", "emotional")
    tracks = dl.parse_tsv(text)
    assert [t.jamendo_id for t in tracks] == [948, 5634]
    assert tracks[0].tags == ("background",)
    assert tracks[1].tags == ("documentary", "emotional")


# ------------------------------------------------------------------- license


@pytest.mark.parametrize("code", ["by", "by-sa", "by-nc", "by-nc-sa"])
def test_allowed_licenses_pass(code):
    fields, reason = dl.evaluate(
        api_item(1, license_ccurl=f"http://creativecommons.org/licenses/{code}/3.0/")
    )
    assert reason is None
    assert fields["license_url"].endswith(f"/licenses/{code}/3.0/")


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("http://creativecommons.org/licenses/by-nd/3.0/", dl.LICENSE_ND),
        ("http://creativecommons.org/licenses/by-nc-nd/4.0/", dl.LICENSE_ND),
        ("", dl.LICENSE_UNKNOWN),
        (None, dl.LICENSE_UNKNOWN),
        ("https://example.com/licenses/by/3.0/", dl.LICENSE_UNKNOWN),
        ("http://creativecommons.org/publicdomain/zero/1.0/", dl.LICENSE_UNKNOWN),
    ],
)
def test_rejected_licenses(url, reason):
    fields, got = dl.evaluate(api_item(1, license_ccurl=url))
    assert fields is None
    assert got == reason


def test_nd_flag_in_licenses_block_also_rejects():
    _, reason = dl.evaluate(api_item(1, licenses={"ccnd": "true"}))
    assert reason == dl.LICENSE_ND


@pytest.mark.parametrize(
    ("url", "name"),
    [
        ("http://creativecommons.org/licenses/by-nc-sa/3.0/", "CC BY-NC-SA 3.0"),
        ("https://creativecommons.org/licenses/by/4.0/", "CC BY 4.0"),
        ("http://creativecommons.org/licenses/by-sa/2.5", "CC BY-SA 2.5"),
    ],
)
def test_license_name(url, name):
    assert dl.license_name(url) == name


def test_download_not_allowed_or_missing_link_rejected():
    assert dl.evaluate(api_item(1, audiodownload_allowed=False))[1] == dl.DOWNLOAD_NOT_ALLOWED
    assert dl.evaluate(api_item(1, audiodownload=""))[1] == dl.NO_DOWNLOAD_URL
    assert dl.evaluate(api_item(1, name=""))[1] == dl.MISSING_INFO


def test_tracks_shorter_than_minimum_rejected():
    assert dl.evaluate(api_item(1, duration=32))[1] == dl.TOO_SHORT
    assert dl.evaluate(api_item(1, duration=59))[1] == dl.TOO_SHORT
    assert dl.evaluate(api_item(1, duration=60))[1] is None


# ----------------------------------------------------------------- selection


def test_selection_is_balanced_and_repeatable():
    tracks = make_tracks()
    first = dl.select_candidates(tracks, 140, seed=7)
    again = dl.select_candidates(tracks, 140, seed=7)
    assert [t.jamendo_id for t in first] == [t.jamendo_id for t in again]
    assert len({t.jamendo_id for t in first}) == 140  # no duplicates

    # Each track belongs to exactly one label here, so every label gets 10.
    per_label = {label: 0 for label in dl.SELECT_TAGS}
    for t in first:
        per_label[next(tag for tag in t.tags if tag in per_label)] += 1
    assert set(per_label.values()) == {10}


def test_selection_changes_with_seed_and_keeps_all_tags():
    tracks = make_tracks()
    a = dl.select_candidates(tracks, 28, seed=1)
    b = dl.select_candidates(tracks, 28, seed=2)
    assert [t.jamendo_id for t in a] != [t.jamendo_id for t in b]
    assert all("film" in t.tags for t in a)  # non-selection tags are kept


def test_selection_stops_when_pool_runs_out():
    assert len(dl.select_candidates(make_tracks(per_label=2), 1000)) == 28


# --------------------------------------------------------------- run / resume


def run_download(fake: FakeJamendo, music_dir: Path, candidates, target=10, dry_run=False):
    return dl.run(fake.client(), music_dir, candidates, target, dry_run, out=lambda _m: None)


def test_run_downloads_writes_manifest_and_counts_rejections(tmp_path):
    cands = [dl.MtgTrack(i, ("happy", "film")) for i in (1, 2, 3, 4)]
    fake = FakeJamendo(
        {
            1: api_item(1),
            2: api_item(2, license_ccurl="http://creativecommons.org/licenses/by-nd/3.0/"),
            3: api_item(3, audiodownload_allowed=False),
            # 4 is missing from the API: removed track
        }
    )
    summary = run_download(fake, tmp_path, cands)
    assert summary.accepted == 1
    assert dict(summary.rejected) == {
        dl.LICENSE_ND: 1,
        dl.DOWNLOAD_NOT_ALLOWED: 1,
        dl.NOT_FOUND: 1,
    }
    assert (tmp_path / "audio" / "1.mp3").read_bytes().startswith(b"ID3")
    assert not list((tmp_path / "audio").glob("*.part"))
    entry = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["tracks"][0]
    assert entry["source_track_id"] == "1"
    assert entry["license"] == "CC BY-NC-SA 3.0"
    assert entry["source_url"] == "https://www.jamendo.com/track/1"
    assert entry["mood_tags"] == ["happy", "film"]  # all tags are kept
    assert entry["file"] == "1.mp3"


def test_request_sends_limit_equal_to_id_count(tmp_path):
    cands = [dl.MtgTrack(i, ("happy",)) for i in range(1, 8)]
    fake = FakeJamendo({i: api_item(i) for i in range(1, 8)})
    run_download(fake, tmp_path, cands, dry_run=True)
    params = fake.api_requests[0].url.params
    assert params["limit"] == "7"
    assert params["audioformat"] == "mp31"
    assert params["include"] == "licenses"


def test_stops_at_target(tmp_path):
    cands = [dl.MtgTrack(i, ("happy",)) for i in range(1, 6)]
    fake = FakeJamendo({i: api_item(i) for i in range(1, 6)})
    summary = run_download(fake, tmp_path, cands, target=2)
    assert summary.accepted == 2
    assert len(fake.audio_requests) == 2


def test_existing_file_is_not_downloaded_again(tmp_path):
    (tmp_path / "audio").mkdir()
    (tmp_path / "audio" / "1.mp3").write_bytes(b"ID3already")
    fake = FakeJamendo({1: api_item(1)})
    run_download(fake, tmp_path, [dl.MtgTrack(1, ("happy",))])
    assert fake.audio_requests == []
    assert (tmp_path / "audio" / "1.mp3").read_bytes() == b"ID3already"
    assert "1" in dl.load_manifest(tmp_path / "manifest.json")


def test_empty_file_is_downloaded_again(tmp_path):
    (tmp_path / "audio").mkdir()
    (tmp_path / "audio" / "1.mp3").write_bytes(b"")
    fake = FakeJamendo({1: api_item(1)})
    run_download(fake, tmp_path, [dl.MtgTrack(1, ("happy",))])
    assert len(fake.audio_requests) == 1
    assert (tmp_path / "audio" / "1.mp3").stat().st_size > 0


def test_manifest_resumes_where_it_stopped(tmp_path):
    cands = [dl.MtgTrack(i, ("happy",)) for i in range(1, 5)]
    fake = FakeJamendo({i: api_item(i) for i in range(1, 5)})
    run_download(fake, tmp_path, cands, target=2)  # "interrupted" after 2

    second = FakeJamendo({i: api_item(i) for i in range(1, 5)})
    summary = run_download(second, tmp_path, cands, target=4)
    assert summary.already_have == 2
    assert summary.accepted == 4
    assert len(second.audio_requests) == 2  # only the missing ones
    assert set(dl.load_manifest(tmp_path / "manifest.json")) == {"1", "2", "3", "4"}


def test_short_track_already_in_manifest_is_removed(tmp_path):
    run_download(
        FakeJamendo({1: api_item(1), 2: api_item(2)}),
        tmp_path,
        [
            dl.MtgTrack(1, ("happy",)),
            dl.MtgTrack(2, ("happy",)),
        ],
    )
    manifest = tmp_path / "manifest.json"
    entries = dl.load_manifest(manifest)
    entries["1"]["duration_seconds"] = 32.0  # saved before the duration rule existed
    dl.save_manifest(manifest, entries)

    summary = run_download(FakeJamendo(), tmp_path, [dl.MtgTrack(1, ("happy",))], target=0)
    assert set(dl.load_manifest(manifest)) == {"2"}
    assert not (tmp_path / "audio" / "1.mp3").exists()
    assert (tmp_path / "audio" / "2.mp3").exists()
    assert summary.accepted == 1


def test_dry_run_writes_nothing(tmp_path):
    cands = [dl.MtgTrack(i, ("happy",)) for i in range(1, 4)]
    fake = FakeJamendo({i: api_item(i) for i in range(1, 4)})
    summary = run_download(fake, tmp_path, cands, dry_run=True)
    assert summary.accepted == 3
    assert fake.audio_requests == []
    assert list(tmp_path.iterdir()) == []


# -------------------------------------------------------------------- errors


def test_api_is_retried_then_succeeds():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"headers": {"status": "success"}, "results": []})

    client = dl.JamendoClient(
        httpx.Client(transport=httpx.MockTransport(handler)), "SECRETKEY", sleep=lambda _s: None
    )
    assert client.fetch_tracks([1]) == []
    assert len(calls) == 3


def test_error_message_hides_client_id():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = dl.JamendoClient(
        httpx.Client(transport=httpx.MockTransport(handler)), "SECRETKEY", sleep=lambda _s: None
    )
    with pytest.raises(dl.DownloadError) as info:
        client.fetch_tracks([1])
    assert "SECRETKEY" not in str(info.value)


def test_redact():
    text = "GET https://api.jamendo.com/v3.0/tracks/?client_id=SECRETKEY&format=json failed"
    assert "SECRETKEY" not in dl.redact(text, "SECRETKEY")
    assert "SECRETKEY" not in dl.redact("key SECRETKEY here", "SECRETKEY")


def test_failed_audio_download_leaves_no_partial_file(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.jamendo.com":
            body = {"headers": {"status": "success"}, "results": [api_item(1)]}
            return httpx.Response(200, json=body)
        return httpx.Response(404)

    client = dl.JamendoClient(
        httpx.Client(transport=httpx.MockTransport(handler)), "SECRETKEY", sleep=lambda _s: None
    )
    summary = dl.run(client, tmp_path, [dl.MtgTrack(1, ("happy",))], 5, False, out=lambda _m: None)
    assert summary.rejected[dl.DOWNLOAD_FAILED] == 1
    assert list((tmp_path / "audio").iterdir()) == []
    assert dl.load_manifest(tmp_path / "manifest.json") == {}


def test_tsv_is_cached(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, content=TSV_HEADER.encode() + tsv_line(1, "happy").encode())

    http = httpx.Client(transport=httpx.MockTransport(handler))
    path = dl.ensure_tsv(http, tmp_path / "cache")
    dl.ensure_tsv(http, tmp_path / "cache")
    assert len(calls) == 1
    assert dl.parse_tsv(path.read_text(encoding="utf-8"))[0].jamendo_id == 1


def test_empty_answer_for_large_batch_is_retried():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        results = [] if len(calls) < 3 else [api_item(1)]
        return httpx.Response(200, json={"headers": {"status": "success"}, "results": results})

    client = dl.JamendoClient(
        httpx.Client(transport=httpx.MockTransport(handler)), "SECRETKEY", sleep=lambda _s: None
    )
    assert len(client.fetch_tracks(list(range(1, 51)))) == 1
    assert len(calls) == 3


def test_empty_answer_for_tiny_batch_is_trusted():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"headers": {"status": "success"}, "results": []})

    client = dl.JamendoClient(
        httpx.Client(transport=httpx.MockTransport(handler)), "SECRETKEY", sleep=lambda _s: None
    )
    assert client.fetch_tracks([1]) == []
    assert len(calls) == 1
