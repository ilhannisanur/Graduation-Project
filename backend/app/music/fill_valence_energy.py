"""Fill `tracks.valence` and `tracks.arousal` (energy) from the mood tags.

Run from the backend folder:
    python -m app.music.fill_valence_energy

The run is repeatable. Rows whose values came from the tags (or are still empty) are recomputed,
so a changed mapping table takes effect. Rows whose values came from another source, such as the
audio model (#20), are left alone.
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.music.models import TrackRow
from app.music.mood_valence import SOURCE_TAGS, estimate_valence_energy


@dataclass
class FillSummary:
    filled: int = 0  # empty before, has values now
    updated: int = 0  # values changed
    unchanged: int = 0
    no_estimate: int = 0  # no known tag: values stay empty


def fill_valence_energy(session: Session) -> FillSummary:
    """Write the estimates to the tracks. The caller commits."""
    summary = FillSummary()
    rows = session.scalars(
        select(TrackRow).where(
            or_(TrackRow.affect_source.is_(None), TrackRow.affect_source == SOURCE_TAGS)
        )
    )
    for row in rows:
        estimate = estimate_valence_energy(row.mood_tags)
        if estimate is None:
            summary.no_estimate += 1
            continue

        valence, energy = estimate
        if row.valence is None:
            summary.filled += 1
        elif (row.valence, row.arousal) != (valence, energy):
            summary.updated += 1
        else:
            summary.unchanged += 1
            continue
        row.valence, row.arousal, row.affect_source = valence, energy, SOURCE_TAGS

    session.flush()
    return summary


def print_summary(summary: FillSummary, out: Callable[[str], None] = print) -> None:
    out("")
    out("=== Valence/energy summary ===")
    out(f"Filled:      {summary.filled}")
    out(f"Updated:     {summary.updated}")
    out(f"Unchanged:   {summary.unchanged}")
    out(f"No estimate: {summary.no_estimate}")


def main() -> int:
    with Session(get_engine()) as session:
        summary = fill_valence_energy(session)
        session.commit()
    print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
