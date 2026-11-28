"""Loudness and silences of the catalog's audio, and how the player gets them."""

import asyncio
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app.music import TrackRow, curate
from app.music.audio_analysis import (
    MAX_BOOST_DB,
    MAX_CUT_DB,
    TARGET_DB,
    Playback,
    analyse,
    analyse_file,
)
from app.music.source import playback_from_row
from app.radio.planner import (
    AnnouncementPlan,
    BroadcastPlanner,
    PlannerSettings,
    SpeechAudio,
    TrackInfo,
    TrackPlayback,
)

RATE = 22_050


def tone(seconds: float, db: float) -> np.ndarray:
    """A 440 Hz sine whose RMS level is `db` dBFS."""
    t = np.arange(int(seconds * RATE)) / RATE
    amplitude = 10 ** (db / 20) * np.sqrt(2)
    return (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * RATE), dtype=np.float32)


# ------------------------------------------------------------------ analysis


def test_a_quiet_song_is_turned_up_and_a_loud_one_down():
    quiet = analyse(tone(30, -20), RATE)
    loud = analyse(tone(30, -10), RATE)

    assert quiet.gain_db == pytest.approx(TARGET_DB + 20, abs=0.3)  # -20 -> -16: +4
    assert loud.gain_db == pytest.approx(TARGET_DB + 10, abs=0.3)  # -10 -> -16: -6


def test_boost_and_cut_are_limited():
    assert analyse(tone(30, -40), RATE).gain_db == MAX_BOOST_DB
    assert analyse(tone(30, -1), RATE).gain_db >= MAX_CUT_DB


def test_silence_at_both_ends_is_found():
    song = np.concatenate([silence(1.5), tone(40, -14), silence(12)])

    result = analyse(song, RATE)

    assert result.start_s == pytest.approx(1.5, abs=0.1)
    assert result.end_s == pytest.approx(41.5, abs=0.1)


def test_a_quiet_tail_far_below_the_song_counts_as_ended():
    song = np.concatenate([tone(40, -14), tone(8, -50)])  # 36 dB below: a fading tail

    assert analyse(song, RATE).end_s == pytest.approx(40, abs=0.1)


def test_quiet_passages_inside_the_song_do_not_end_it():
    song = np.concatenate([tone(20, -14), tone(10, -30), tone(20, -14)])

    assert analyse(song, RATE).end_s == pytest.approx(50, abs=0.1)


def test_silent_or_odd_files_are_played_as_they_are():
    assert analyse(silence(20), RATE) == Playback(gain_db=0.0, start_s=0.0, end_s=20.0)
    short = analyse(np.concatenate([silence(10), tone(3, -14), silence(10)]), RATE)
    assert (short.start_s, short.end_s) == (0.0, 23.0)  # 3 s of music: something is off


def test_files_are_decoded_and_stereo_is_mixed_down(tmp_path: Path):
    mono = np.concatenate([silence(2), tone(30, -20)])
    path = tmp_path / "song.wav"
    sf.write(path, np.stack([mono, mono], axis=1), RATE)

    result = analyse_file(path)

    assert result.start_s == pytest.approx(2, abs=0.1)
    assert result.gain_db == pytest.approx(4, abs=0.3)


# ---------------------------------------------------------- catalog command


def test_analyze_measures_only_new_tracks_unless_told(db_session, tmp_path: Path):
    def row(source_id: str, gain: float | None) -> TrackRow:
        return TrackRow(
            source="test-analysis",
            source_track_id=source_id,
            title="T",
            artist="A",
            duration_seconds=60,
            license="CC BY 4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            source_url="https://example.org",
            file_path=f"audio/{source_id}.mp3",
            gain_db=gain,
        )

    new, done = row("new", None), row("done", 1.0)
    db_session.add_all([new, done])
    db_session.flush()
    measured: list[str] = []

    def fake_measure(path: Path) -> Playback:
        measured.append(path.name)
        return Playback(gain_db=-3.0, start_s=0.4, end_s=55.0)

    curate.analyze(db_session, tmp_path, measure=fake_measure, out=lambda _m: None)

    assert "new.mp3" in measured and "done.mp3" not in measured
    assert (new.gain_db, new.start_s, new.end_s) == (-3.0, 0.4, 55.0)
    assert done.gain_db == 1.0

    curate.analyze(db_session, tmp_path, everything=True, measure=fake_measure, out=lambda _m: None)
    assert done.gain_db == -3.0


def test_a_broken_file_does_not_stop_the_others(db_session, tmp_path: Path):
    rows = [
        TrackRow(
            source="test-analysis",
            source_track_id=name,
            title="T",
            artist="A",
            duration_seconds=60,
            license="CC BY 4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            source_url="https://example.org",
            file_path=f"audio/{name}.mp3",
        )
        for name in ("broken", "fine")
    ]
    db_session.add_all(rows)
    db_session.flush()

    def measure(path: Path) -> Playback:
        if path.name == "broken.mp3":
            raise RuntimeError("cannot decode")
        return Playback(gain_db=2.0, start_s=0.0, end_s=50.0)

    curate.analyze(db_session, tmp_path, measure=measure, out=lambda _m: None)

    assert rows[0].gain_db is None
    assert rows[1].gain_db == 2.0


# ------------------------------------------------------------- to the player


def test_playback_comes_from_the_row_once_measured():
    assert playback_from_row(None) is None
    assert playback_from_row(TrackRow(gain_db=None)) is None
    assert playback_from_row(TrackRow(gain_db=-2.5, start_s=None, end_s=170.0)) == TrackPlayback(
        gain_db=-2.5, start_s=0.0, end_s=170.0
    )


def test_the_planner_hands_playback_to_the_player():
    playback = TrackPlayback(gain_db=-4.0, start_s=1.2, end_s=171.0)

    class Music:
        async def next_track(self, *, user_id, recent_track_ids) -> TrackInfo:
            return TrackInfo(
                track_id="t1", title="S", artist="A", duration_s=180, playback=playback
            )

    class Director:
        async def plan(self, request) -> AnnouncementPlan:
            return AnnouncementPlan(text="Hello there.")

    class Speech:
        async def synthesize(self, plan) -> SpeechAudio:
            return SpeechAudio(audio_url="/speech/1.wav", duration_s=1.0)

    async def scenario():
        planner = BroadcastPlanner(
            music=Music(), director=Director(), speech=Speech(), settings=PlannerSettings()
        )
        session = planner.create_session("u1")
        first = await planner.next_segment(session.session_id)
        await planner.aclose()
        return first

    first = asyncio.run(scenario())
    assert first.segment.kind == "track"
    assert first.segment.playback == playback
