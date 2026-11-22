from sqlalchemy.orm import Session

from app.music import TrackRow
from app.music.fill_valence_energy import fill_valence_energy
from app.music.mood_valence import TAG_VALENCE_ENERGY, estimate_valence_energy


def make_track(source_id: str, tags: list[str], **overrides) -> TrackRow:
    return TrackRow(
        title=f"Song {source_id}",
        artist="Some Artist",
        duration_seconds=120.0,
        license="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        source_url=f"https://example.org/track/{source_id}",
        mood_tags=tags,
        source="test-valence",
        source_track_id=source_id,
        **overrides,
    )


def test_table_values_are_in_range():
    for tag, (valence, energy) in TAG_VALENCE_ENERGY.items():
        assert 0 <= valence <= 1, tag
        assert 0 <= energy <= 1, tag


def test_single_tag_uses_table_value():
    assert estimate_valence_energy(["calm"]) == (0.6, 0.1)


def test_calm_is_low_energy_and_happy_is_high_valence():
    calm_valence, calm_energy = estimate_valence_energy(["calm"])
    happy_valence, happy_energy = estimate_valence_energy(["happy"])
    assert calm_energy < happy_energy
    assert happy_valence > estimate_valence_energy(["sad"])[0]


def test_several_tags_are_averaged():
    valence, energy = estimate_valence_energy(["happy", "sad"])
    assert valence == round((0.85 + 0.12) / 2, 3)
    assert energy == round((0.65 + 0.25) / 2, 3)


def test_unknown_tags_are_ignored_and_no_known_tag_gives_none():
    assert estimate_valence_energy(["calm", "no-such-tag"]) == estimate_valence_energy(["calm"])
    assert estimate_valence_energy(["no-such-tag"]) is None
    assert estimate_valence_energy([]) is None


def test_fill_sets_values_and_source(db_session: Session):
    db_session.add_all([make_track("1", ["calm"]), make_track("2", [])])
    db_session.flush()

    summary = fill_valence_energy(db_session)

    rows = {
        r.source_track_id: r for r in db_session.query(TrackRow).filter_by(source="test-valence")
    }
    assert (rows["1"].valence, rows["1"].arousal, rows["1"].affect_source) == (0.6, 0.1, "tags")
    assert (rows["2"].valence, rows["2"].arousal, rows["2"].affect_source) == (None, None, None)
    assert summary.filled >= 1 and summary.no_estimate >= 1


def test_second_run_changes_nothing(db_session: Session):
    db_session.add(make_track("1", ["calm"]))
    db_session.flush()
    fill_valence_energy(db_session)

    summary = fill_valence_energy(db_session)

    assert (summary.filled, summary.updated) == (0, 0)
    assert summary.unchanged >= 1


def test_values_from_another_source_are_not_overwritten(db_session: Session):
    db_session.add(make_track("1", ["calm"], valence=0.9, arousal=0.9, affect_source="audio"))
    db_session.flush()

    fill_valence_energy(db_session)

    row = db_session.query(TrackRow).filter_by(source="test-valence").one()
    assert (row.valence, row.arousal, row.affect_source) == (0.9, 0.9, "audio")
