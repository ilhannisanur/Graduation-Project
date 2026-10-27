"""Import the downloaded catalog (manifest.json) into the `tracks` table.

Run from the backend folder:
    python -m app.music.import_catalog

The run is repeatable: a track is identified by (source, source_track_id), so a second run adds
nothing and only updates tracks whose manifest data changed. Tracks whose audio file is missing
from disk are skipped and reported.
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_engine
from app.music.download import load_manifest
from app.music.models import TrackRow

# Manifest keys copied to the matching TrackRow columns.
SYNCED_FIELDS = (
    "title",
    "artist",
    "duration_seconds",
    "license",
    "license_url",
    "source_url",
    "mood_tags",
)


@dataclass
class ImportSummary:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: list[str] = field(default_factory=list)  # source_track_ids with no audio file


def import_catalog(
    session: Session,
    music_dir: Path,
    out: Callable[[str], None] = print,
) -> ImportSummary:
    """Write the manifest entries to the database. The caller commits."""
    summary = ImportSummary()
    entries = load_manifest(music_dir / "manifest.json")
    existing = {
        (row.source, row.source_track_id): row
        for row in session.scalars(select(TrackRow).where(TrackRow.source.in_(_sources(entries))))
    }

    for entry in entries.values():
        source, source_id = entry["source"], entry["source_track_id"]
        audio = music_dir / "audio" / entry["file"]
        if not (audio.exists() and audio.stat().st_size > 0):
            summary.skipped.append(source_id)
            out(f"Skipped {source_id}: audio file {audio.name} is missing.")
            continue

        # Relative to the music folder, so the catalog still works if the folder moves.
        values = {name: entry[name] for name in SYNCED_FIELDS}
        values["file_path"] = f"audio/{entry['file']}"

        row = existing.get((source, source_id))
        if row is None:
            session.add(TrackRow(source=source, source_track_id=source_id, **values))
            summary.added += 1
            continue

        changed = [name for name, value in values.items() if getattr(row, name) != value]
        for name in changed:
            setattr(row, name, values[name])
        if changed:
            summary.updated += 1
        else:
            summary.unchanged += 1

    session.flush()
    return summary


def _sources(entries: dict[str, dict]) -> set[str]:
    return {entry["source"] for entry in entries.values()}


def print_summary(summary: ImportSummary, out: Callable[[str], None] = print) -> None:
    out("")
    out("=== Import summary ===")
    out(f"Added:     {summary.added}")
    out(f"Updated:   {summary.updated}")
    out(f"Unchanged: {summary.unchanged}")
    out(f"Skipped:   {len(summary.skipped)}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    music_dir = get_settings().music_dir
    if not (music_dir / "manifest.json").exists():
        print(f"No manifest at {music_dir / 'manifest.json'}. Run app.music.download first.")
        return 1

    with Session(get_engine()) as session:
        summary = import_catalog(session, music_dir)
        session.commit()
    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
