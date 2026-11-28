"""Download Creative Commons tracks from Jamendo with their license info.

Run from the backend folder:
    python -m app.music.download [--target 400] [--candidates 1500] [--dry-run]
    python -m app.music.download --popular [--add 200] [--dry-run]

Candidates come from the MTG-Jamendo mood/theme list; every candidate is re-checked against the
Jamendo API (see docs/muzik-kaynagi.md). With --popular they are Jamendo's most listened tracks
that are also on that list (#107). The run is repeatable: files and manifest entries that
already exist are kept, so an interrupted run continues where it stopped. Tracks listed under
"removed" in the manifest (see app.music.curate) are never downloaded again.
"""

import argparse
import json
import os
import random
import re
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.core.config import get_settings

MTG_TSV_URL = (
    "https://raw.githubusercontent.com/MTG/mtg-jamendo-dataset/master/data/"
    "autotagging_moodtheme.tsv"
)
JAMENDO_TRACKS_URL = "https://api.jamendo.com/v3.0/tracks/"
TAG_PREFIX = "mood/theme---"
AUDIO_FORMAT = "mp31"  # 96 kbps; also decides the format of `audiodownload`
SEED = 42
BATCH_SIZE = 50  # ids per request (API limit is 200; keep the URL short)
REQUEST_DELAY = 0.5  # seconds between API requests
MAX_ATTEMPTS = 6  # the empty-answer glitch below can last several tries in a row
# The API sometimes answers "success" with no results at all; for batches this big that is a
# glitch (a real batch cannot be entirely removed), so it is retried instead of trusted.
EMPTY_IS_SUSPICIOUS_FROM = 6
# Shorter pieces are jingles rather than songs and sound odd on air.
MIN_DURATION_SECONDS = 60
POPULAR_PAGE = 200  # tracks per page of the popular list (the API maximum)

# Tags used for candidate selection (see docs/muzik-kaynagi.md, section 4).
SELECT_TAGS = (
    "happy",
    "sad",
    "relaxing",
    "calm",
    "energetic",
    "dark",
    "dramatic",
    "uplifting",
    "melancholic",
    "romantic",
    "epic",
    "positive",
    "soft",
    "upbeat",
)

# Reasons a candidate is dropped (keys of the summary).
NOT_FOUND = "not_found"
LICENSE_UNKNOWN = "license_missing_or_not_cc"
LICENSE_ND = "license_nd"
DOWNLOAD_NOT_ALLOWED = "download_not_allowed"
NO_DOWNLOAD_URL = "no_download_url"
MISSING_INFO = "missing_title_artist_or_duration"
TOO_SHORT = "too_short"
DOWNLOAD_FAILED = "audio_download_failed"

_LICENSE_RE = re.compile(
    r"^https?://(?:www\.)?creativecommons\.org/licenses/([a-z\-]+)/([0-9.]+)/?", re.IGNORECASE
)
_CLIENT_ID_RE = re.compile(r"client_id=[^&\s'\"]+")


class DownloadError(Exception):
    """Raised for network/API failures. The message never contains the API key."""


@dataclass(frozen=True)
class MtgTrack:
    jamendo_id: int
    tags: tuple[str, ...]  # all mood/theme tags of the track, prefix removed


@dataclass
class Summary:
    candidates: int = 0
    already_have: int = 0
    accepted: int = 0
    rejected: Counter = field(default_factory=Counter)


# ---------------------------------------------------------------- candidates


def parse_tsv(text: str) -> list[MtgTrack]:
    """Parse autotagging_moodtheme.tsv. Tags are the tab-separated columns after DURATION."""
    tracks: list[MtgTrack] = []
    for line in text.splitlines()[1:]:  # skip header
        cols = line.rstrip("\r\n").split("\t")
        if len(cols) < 6 or not cols[0].startswith("track_"):
            continue
        tags = tuple(c.removeprefix(TAG_PREFIX) for c in cols[5:] if c)
        tracks.append(MtgTrack(jamendo_id=int(cols[0].removeprefix("track_")), tags=tags))
    return tracks


def select_candidates(
    tracks: list[MtgTrack], count: int, seed: int = SEED, labels: tuple[str, ...] = SELECT_TAGS
) -> list[MtgTrack]:
    """Pick `count` tracks, taking turns between labels so each label gets an equal share.

    A track is assigned to one label only (no duplicates) but keeps all its tags. The result
    is ordered round-robin, so processing it in order keeps the labels balanced at any cut-off.
    The same input and seed always give the same list.
    """
    rng = random.Random(seed)
    pools: dict[str, list[MtgTrack]] = {}
    for label in labels:
        pool = sorted((t for t in tracks if label in t.tags), key=lambda t: t.jamendo_id)
        rng.shuffle(pool)
        pools[label] = pool

    cursors = dict.fromkeys(labels, 0)
    used: set[int] = set()
    chosen: list[MtgTrack] = []
    while len(chosen) < count:
        progressed = False
        for label in labels:
            if len(chosen) >= count:
                break
            pool, i = pools[label], cursors[label]
            while i < len(pool) and pool[i].jamendo_id in used:
                i += 1
            if i < len(pool):
                used.add(pool[i].jamendo_id)
                chosen.append(pool[i])
                progressed = True
                i += 1
            cursors[label] = i
        if not progressed:
            break
    return chosen


def popular_candidates(tracks: list[MtgTrack], popular_ids: list[int]) -> list[MtgTrack]:
    """The MTG tracks among Jamendo's popular ones, in popularity order.

    Only tracks of the MTG mood list are taken: their mood tags give valence/energy (#75),
    which the mood picker needs. The same id is never listed twice.
    """
    by_id = {t.jamendo_id: t for t in tracks}
    chosen: list[MtgTrack] = []
    seen: set[int] = set()
    for jamendo_id in popular_ids:
        if jamendo_id in by_id and jamendo_id not in seen:
            seen.add(jamendo_id)
            chosen.append(by_id[jamendo_id])
    return chosen


# ------------------------------------------------------------------- license


def license_name(url: str) -> str | None:
    """'http://creativecommons.org/licenses/by-nc-sa/3.0/' -> 'CC BY-NC-SA 3.0'."""
    match = _LICENSE_RE.match((url or "").strip())
    if not match:
        return None
    return f"CC {match.group(1).upper()} {match.group(2)}"


def evaluate(item: dict) -> tuple[dict | None, str | None]:
    """Apply the elimination rules to one Jamendo API result.

    Returns (fields, None) for an accepted track or (None, reason) for a rejected one.
    """
    license_url = (item.get("license_ccurl") or "").strip()
    name = license_name(license_url)
    if name is None:
        return None, LICENSE_UNKNOWN
    path = license_url.split("/licenses/", 1)[1].split("/")[0]
    flags = item.get("licenses") or {}
    if "nd" in path.lower().split("-") or str(flags.get("ccnd")).lower() == "true":
        return None, LICENSE_ND
    if not item.get("audiodownload_allowed"):
        return None, DOWNLOAD_NOT_ALLOWED
    download_url = (item.get("audiodownload") or "").strip()
    if not download_url:
        return None, NO_DOWNLOAD_URL
    title = (item.get("name") or "").strip()
    artist = (item.get("artist_name") or "").strip()
    duration = item.get("duration")
    source_url = (item.get("shareurl") or "").strip()
    if not title or not artist or not duration or not source_url:
        return None, MISSING_INFO
    if float(duration) < MIN_DURATION_SECONDS:
        return None, TOO_SHORT
    fields = {
        "title": title,
        "artist": artist,
        "duration_seconds": float(duration),
        "license": name,
        "license_url": license_url,
        "source_url": source_url,
        "download_url": download_url,
        **listening_info(item),
    }
    return fields, None


def listening_info(item: dict) -> dict:
    """Listen count, sung or instrumental, and genres from a result asked with
    include=stats musicinfo. Missing parts come back as None / []."""
    stats = item.get("stats") or {}
    music = item.get("musicinfo") or {}
    listens = stats.get("rate_listened_total")
    kind = music.get("vocalinstrumental")
    genres = (music.get("tags") or {}).get("genres") or []
    return {
        "listens": int(listens) if isinstance(listens, int | float) else None,
        "has_vocals": {"vocal": True, "instrumental": False}.get(kind),
        "genres": [str(g) for g in genres],
    }


# ------------------------------------------------------------------- network


def redact(text: str, client_id: str = "") -> str:
    """Hide the API key in any text (e.g. URLs in error messages)."""
    text = _CLIENT_ID_RE.sub("client_id=***", text)
    return text.replace(client_id, "***") if client_id else text


class JamendoClient:
    def __init__(
        self,
        http: httpx.Client,
        client_id: str,
        sleep: Callable[[float], None] = time.sleep,
        delay: float = REQUEST_DELAY,
    ) -> None:
        self.http = http
        self.client_id = client_id
        self.sleep = sleep
        self.delay = delay
        self._made_request = False

    def _retry(self, action: Callable[[], object]):
        last = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return action()
            except (httpx.HTTPError, ValueError) as exc:
                last = redact(f"{type(exc).__name__}: {exc}", self.client_id)
                if attempt < MAX_ATTEMPTS:
                    self.sleep(2.0 * attempt)
        raise DownloadError(f"failed after {MAX_ATTEMPTS} attempts: {last}")

    def fetch_tracks(self, ids: list[int]) -> list[dict]:
        """Ask the API about several tracks in one request."""
        if self._made_request:
            self.sleep(self.delay)
        self._made_request = True
        params = {
            "client_id": self.client_id,
            "format": "json",
            # A space is sent as "+", which is how the API separates ids.
            "id": " ".join(str(i) for i in ids),
            "include": "licenses stats musicinfo",
            "audioformat": AUDIO_FORMAT,
            "limit": len(ids),  # the default limit is small and would cut results silently
        }

        def call() -> list[dict]:
            response = self.http.get(JAMENDO_TRACKS_URL, params=params)
            response.raise_for_status()
            body = response.json()
            headers = body.get("headers") or {}
            if headers.get("status") != "success":
                # ValueError is retried, then reported without the key.
                raise ValueError(f"API error: {headers.get('error_message')}")
            results = body.get("results") or []
            if not results and len(ids) >= EMPTY_IS_SUSPICIOUS_FROM:
                raise ValueError("API returned no results for a large batch")
            return results

        try:
            return self._retry(call)
        except DownloadError as exc:
            raise DownloadError(f"Jamendo request for {len(ids)} ids {exc}") from None

    def popular_ids(self, vocalinstrumental: str, count: int) -> list[int]:
        """Ids of Jamendo's most listened tracks, most popular first.

        `vocalinstrumental` is "vocal" or "instrumental". Licenses are not checked here; the
        normal per-track check does that later.
        """
        ids: list[int] = []
        for offset in range(0, count, POPULAR_PAGE):
            if self._made_request:
                self.sleep(self.delay)
            self._made_request = True
            params = {
                "client_id": self.client_id,
                "format": "json",
                "order": "popularity_total",
                "vocalinstrumental": vocalinstrumental,
                "limit": POPULAR_PAGE,
                "offset": offset,
            }

            def call(params=params) -> list[dict]:
                response = self.http.get(JAMENDO_TRACKS_URL, params=params)
                response.raise_for_status()
                body = response.json()
                if (body.get("headers") or {}).get("status") != "success":
                    raise ValueError("API error on the popular list")
                results = body.get("results") or []
                if not results:
                    raise ValueError("API returned an empty page of the popular list")
                return results

            try:
                page = self._retry(call)
            except DownloadError as exc:
                raise DownloadError(f"Jamendo popular list at {offset} {exc}") from None
            ids.extend(int(item["id"]) for item in page)
        return ids

    def download_audio(self, url: str, dest: Path) -> int:
        """Stream a file to `dest` via a temporary name; returns its size in bytes."""
        tmp = dest.with_name(dest.name + ".part")

        def call() -> int:
            size = 0
            with self.http.stream("GET", url, follow_redirects=True) as response:
                response.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)
                        size += len(chunk)
            if size == 0:
                raise ValueError("empty response")
            os.replace(tmp, dest)
            return size

        try:
            return self._retry(call)  # type: ignore[return-value]
        except DownloadError as exc:
            tmp.unlink(missing_ok=True)
            raise DownloadError(f"audio download {exc}") from None


def ensure_tsv(http: httpx.Client, cache_dir: Path) -> Path:
    """Download the MTG tag list once; later runs reuse the cached file."""
    path = cache_dir / "autotagging_moodtheme.tsv"
    if path.exists() and path.stat().st_size > 0:
        return path
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        response = http.get(MTG_TSV_URL, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise DownloadError(f"could not download the MTG tag list: {type(exc).__name__}") from None
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(response.content)
    os.replace(tmp, path)
    return path


# ------------------------------------------------------------------ manifest


def load_manifest(path: Path) -> dict[str, dict]:
    """Existing manifest entries keyed by source_track_id (empty if there is none)."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {entry["source_track_id"]: entry for entry in data.get("tracks", [])}


def load_removed(path: Path) -> dict[str, str]:
    """Tracks taken out of the catalog on purpose (source_track_id -> reason). Downloads skip
    them, so a later run does not bring them back."""
    if not path.exists():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")).get("removed", {}))


def save_manifest(
    path: Path, entries: dict[str, dict], removed: dict[str, str] | None = None
) -> None:
    """Write the manifest through a temporary file so a crash never leaves a broken one.
    `removed` replaces the list of removed tracks; None keeps the one on disk."""
    if removed is None:
        removed = load_removed(path)
    tmp = path.with_name(path.name + ".tmp")
    payload = {
        "version": 1,
        "source": "jamendo",
        "tracks": list(entries.values()),
        "removed": removed,
    }
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# ----------------------------------------------------------------------- run


def run(
    jamendo: JamendoClient,
    music_dir: Path,
    candidates: list[MtgTrack],
    target: int,
    dry_run: bool,
    out: Callable[[str], None] = print,
) -> Summary:
    audio_dir = music_dir / "audio"
    manifest_path = music_dir / "manifest.json"
    entries = {} if dry_run else load_manifest(manifest_path)
    if not dry_run:
        audio_dir.mkdir(parents=True, exist_ok=True)
        # Entries saved before the duration rule existed are dropped so the catalog follows it.
        too_short = [k for k, e in entries.items() if e["duration_seconds"] < MIN_DURATION_SECONDS]
        for key in too_short:
            (audio_dir / entries.pop(key)["file"]).unlink(missing_ok=True)
            out(f"Removed {key}: shorter than {MIN_DURATION_SECONDS} seconds.")
        if too_short:
            save_manifest(manifest_path, entries)

    summary = Summary(candidates=len(candidates))
    removed = load_removed(manifest_path)
    todo = [
        c
        for c in candidates
        if str(c.jamendo_id) not in entries and str(c.jamendo_id) not in removed
    ]
    summary.already_have = len(candidates) - len(todo)
    summary.accepted = len(entries) if not dry_run else 0
    if summary.already_have:
        out(f"Manifest already has {summary.already_have} of these candidates; skipping them.")

    for start in range(0, len(todo), BATCH_SIZE):
        if summary.accepted >= target:
            break
        batch = todo[start : start + BATCH_SIZE]
        results = {
            str(item.get("id")): item
            for item in jamendo.fetch_tracks([c.jamendo_id for c in batch])
        }
        out(f"Asked about {len(batch)} tracks, got {len(results)} back.")

        for candidate in batch:
            if summary.accepted >= target:
                break
            source_id = str(candidate.jamendo_id)
            item = results.get(source_id)
            fields, reason = evaluate(item) if item else (None, NOT_FOUND)
            if fields is None:
                summary.rejected[reason] += 1
                continue

            filename = f"{source_id}.mp3"
            if not dry_run:
                dest = audio_dir / filename
                if not (dest.exists() and dest.stat().st_size > 0):
                    try:
                        jamendo.download_audio(fields["download_url"], dest)
                    except DownloadError as exc:
                        summary.rejected[DOWNLOAD_FAILED] += 1
                        out(f"  {source_id}: {exc}")
                        continue
                entries[source_id] = {
                    "source": "jamendo",
                    "source_track_id": source_id,
                    "title": fields["title"],
                    "artist": fields["artist"],
                    "duration_seconds": fields["duration_seconds"],
                    "license": fields["license"],
                    "license_url": fields["license_url"],
                    "source_url": fields["source_url"],
                    "mood_tags": list(candidate.tags),
                    "file": filename,
                    "listens": fields["listens"],
                    "has_vocals": fields["has_vocals"],
                    "genres": fields["genres"],
                }
                save_manifest(manifest_path, entries)
            summary.accepted += 1
            out(
                f"[{summary.accepted}/{target}] {source_id} {fields['title']} - "
                f"{fields['artist']} ({fields['license']})"
            )
    return summary


def total_size_bytes(music_dir: Path) -> int:
    entries = load_manifest(music_dir / "manifest.json")
    total = 0
    for entry in entries.values():
        path = music_dir / "audio" / entry["file"]
        if path.exists():
            total += path.stat().st_size
    return total


def print_summary(summary: Summary, music_dir: Path, dry_run: bool, out=print) -> None:
    out("")
    out("=== Summary" + (" (dry run, nothing written)" if dry_run else "") + " ===")
    out(f"Candidates:     {summary.candidates}")
    if summary.already_have:
        out(f"Already in manifest: {summary.already_have}")
    out(f"Accepted:       {summary.accepted}" + (" (would be accepted)" if dry_run else ""))
    out(f"Rejected:       {sum(summary.rejected.values())}")
    for reason, count in summary.rejected.most_common():
        out(f"  {reason}: {count}")
    if not dry_run:
        out(f"Total size:     {total_size_bytes(music_dir) / 1024 / 1024:.1f} MB")
        out(f"Manifest:       {music_dir / 'manifest.json'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download Creative Commons tracks from Jamendo.")
    parser.add_argument("--target", type=int, default=400, help="tracks to keep (default 400)")
    # About 30% of candidates pass the license/availability checks, so 400 needs ~1500.
    parser.add_argument("--candidates", type=int, default=1500, help="candidates (default 1500)")
    parser.add_argument(
        "--dry-run", action="store_true", help="check licenses only; write no audio or manifest"
    )
    parser.add_argument(
        "--popular",
        action="store_true",
        help="add Jamendo's most listened tracks that have MTG mood tags (instead of --target)",
    )
    parser.add_argument(
        "--add", type=int, default=200, help="with --popular: tracks to add at most (default 200)"
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=2000,
        help="with --popular: how far down the popular lists to look (default 2000 sung, "
        "half as many instrumental)",
    )
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # titles may hold characters the console lacks

    settings = get_settings()
    if not settings.jamendo_client_id:
        print("JAMENDO_CLIENT_ID is empty. Set it in backend/.env.", file=sys.stderr)
        return 2
    music_dir = settings.music_dir

    with httpx.Client(timeout=httpx.Timeout(30.0, read=60.0)) as http:
        try:
            tsv_path = ensure_tsv(http, music_dir / "cache")
            tracks = parse_tsv(tsv_path.read_text(encoding="utf-8"))
            jamendo = JamendoClient(http, settings.jamendo_client_id)
            target = args.target
            if args.popular:
                # Sung songs first: the catalog had too many instrumentals (#107).
                ids = jamendo.popular_ids("vocal", args.depth)
                ids += jamendo.popular_ids("instrumental", args.depth // 2)
                candidates = popular_candidates(tracks, ids)
                target = len(load_manifest(music_dir / "manifest.json")) + args.add
                print(f"{len(candidates)} of {len(ids)} popular tracks have MTG mood tags.")
            else:
                candidates = select_candidates(tracks, args.candidates)
                print(f"Selected {len(candidates)} candidates from {len(tracks)} MTG tracks.")
            summary = run(jamendo, music_dir, candidates, target, args.dry_run)
        except DownloadError as exc:
            print(f"Stopped: {exc}", file=sys.stderr)
            print("Run the same command again to continue.", file=sys.stderr)
            return 1
    print_summary(summary, music_dir, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
