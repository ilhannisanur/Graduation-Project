"""Keep the catalog worth listening to (#107).

Run from the backend folder:
    python -m app.music.curate enrich              # listens, sung/instrumental, genres
    python -m app.music.curate prune               # list what would be removed
    python -m app.music.curate prune --apply       # remove it
    python -m app.music.curate analyze [--all]     # loudness and silences of the audio

`enrich` asks the Jamendo API about every track of the manifest and writes what it learns into
the manifest; `python -m app.music.import_catalog` then copies it to the database.

`prune` removes songs few people listen to on Jamendo: the first catalog was mostly such
tracks and sounded like background music rather than radio. Tracks whose listen count is not
known stay.
A removed track leaves the manifest, the audio folder and the database, and is listed under
"removed" in the manifest so a later download does not bring it back. Old song requests for it
keep their text; their link to the track becomes empty.

`analyze` measures every track's audio file (app.music.audio_analysis) and writes gain_db,
start_s and end_s straight to the database; by default only tracks not measured yet.
"""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_engine
from app.music.audio_analysis import Playback, analyse_file
from app.music.download import (
    BATCH_SIZE,
    DownloadError,
    JamendoClient,
    listening_info,
    load_manifest,
    load_removed,
    save_manifest,
)
from app.music.models import TrackRow

# Tracks heard fewer times than this on Jamendo are removed by `prune` (decided 2026-11-28:
# first instrumentals under 5,000, then every track under 10,000).
MIN_LISTENS = 10_000
PRUNE_REASON = "few listens on Jamendo (#107)"


def enrich(jamendo: JamendoClient, music_dir: Path, out: Callable[[str], None] = print) -> int:
    """Fill listens / has_vocals / genres of every manifest entry. Returns how many were filled."""
    manifest_path = music_dir / "manifest.json"
    entries = load_manifest(manifest_path)
    ids = list(entries)
    filled = 0
    for start in range(0, len(ids), BATCH_SIZE):
        batch = ids[start : start + BATCH_SIZE]
        results = {
            str(item.get("id")): item for item in jamendo.fetch_tracks([int(i) for i in batch])
        }
        for source_id in batch:
            item = results.get(source_id)
            if item is None:
                out(f"  {source_id}: no answer from Jamendo, left as it was")
                continue
            entries[source_id].update(listening_info(item))
            filled += 1
        save_manifest(manifest_path, entries)
        out(f"Asked about {len(batch)} tracks, filled {filled} so far.")
    return filled


def prune_candidates(entries: dict[str, dict], min_listens: int = MIN_LISTENS) -> list[dict]:
    """Tracks with fewer listens than `min_listens`. An unknown count is kept."""
    return [
        e for e in entries.values() if e.get("listens") is not None and e["listens"] < min_listens
    ]


def prune(
    session: Session | None,
    music_dir: Path,
    min_listens: int = MIN_LISTENS,
    out: Callable[[str], None] = print,
) -> list[dict]:
    """Remove the prune candidates. With `session` None nothing is changed (a dry run).
    The caller commits the session."""
    manifest_path = music_dir / "manifest.json"
    entries = load_manifest(manifest_path)
    chosen = prune_candidates(entries, min_listens)
    for entry in chosen:
        listens = entry["listens"]
        out(f"  {entry['source_track_id']} {entry['title']} - {entry['artist']} ({listens})")
    if session is None or not chosen:
        return chosen

    removed = load_removed(manifest_path)
    for entry in chosen:
        source_id = entry["source_track_id"]
        entries.pop(source_id)
        removed[source_id] = PRUNE_REASON
        (music_dir / "audio" / entry["file"]).unlink(missing_ok=True)
        session.execute(
            delete(TrackRow).where(
                TrackRow.source == entry["source"], TrackRow.source_track_id == source_id
            )
        )
    save_manifest(manifest_path, entries, removed)
    return chosen


def analyze(
    session: Session,
    music_dir: Path,
    everything: bool = False,
    measure: Callable[[Path], Playback] = analyse_file,
    out: Callable[[str], None] = print,
) -> int:
    """Measure the audio of the tracks (all, or only those not measured yet) and store the
    result on the rows. Returns how many were measured. The caller commits."""
    query = select(TrackRow).where(TrackRow.file_path.is_not(None))
    if not everything:
        query = query.where(TrackRow.gain_db.is_(None))
    rows = list(session.scalars(query))
    measured = 0
    for i, row in enumerate(rows, start=1):
        path = music_dir / row.file_path
        try:
            playback = measure(path)
        except Exception as exc:  # a broken file must not stop the others
            out(f"  {row.source_track_id}: could not read {path.name} ({type(exc).__name__})")
            continue
        row.gain_db, row.start_s, row.end_s = playback.gain_db, playback.start_s, playback.end_s
        measured += 1
        if i % 25 == 0 or i == len(rows):
            out(f"Measured {i}/{len(rows)}")
    session.flush()
    return measured


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Keep the catalog worth listening to.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("enrich", help="fill listens, sung/instrumental and genres from Jamendo")
    analyze_parser = sub.add_parser("analyze", help="measure loudness and silences of the audio")
    analyze_parser.add_argument(
        "--all", action="store_true", help="measure every track again, not only new ones"
    )
    prune_parser = sub.add_parser("prune", help="remove little-listened tracks")
    prune_parser.add_argument("--apply", action="store_true", help="really remove them")
    prune_parser.add_argument(
        "--min-listens",
        type=int,
        default=MIN_LISTENS,
        help=f"tracks below this are removed (default {MIN_LISTENS})",
    )
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    settings = get_settings()
    music_dir = settings.music_dir
    if not (music_dir / "manifest.json").exists():
        print(f"No manifest at {music_dir / 'manifest.json'}. Run app.music.download first.")
        return 1

    if args.command == "enrich":
        if not settings.jamendo_client_id:
            print("JAMENDO_CLIENT_ID is empty. Set it in backend/.env.", file=sys.stderr)
            return 2
        with httpx.Client(timeout=httpx.Timeout(30.0, read=60.0)) as http:
            try:
                filled = enrich(JamendoClient(http, settings.jamendo_client_id), music_dir)
            except DownloadError as exc:
                print(f"Stopped: {exc}", file=sys.stderr)
                return 1
        print(f"Filled {filled} tracks. Now run: python -m app.music.import_catalog")
        return 0

    if args.command == "analyze":
        with Session(get_engine()) as session:
            measured = analyze(session, music_dir, everything=args.all)
            session.commit()
        print(f"Measured {measured} tracks.")
        return 0

    if not args.apply:
        chosen = prune(None, music_dir, args.min_listens)
        print(f"\n{len(chosen)} tracks would be removed. Add --apply to remove them.")
        return 0
    with Session(get_engine()) as session:
        chosen = prune(session, music_dir, args.min_listens)
        session.commit()
    print(f"\nRemoved {len(chosen)} tracks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
