"""How loud a song is and where its music really starts and ends.

Measured on 2026-11-28 over 40 catalog songs: loudness differed by up to 16 dB, and 40% of the
songs ended in more than 3 s of near silence (up to 17 s). The player uses the result to play
every song at the same level, skip silence at the start, and time the DJ and crossfades from
the end of the music instead of the end of the file.

The loudness is a simple gated RMS (in the spirit of EBU R128 gating, without its K-weighting),
which is enough to bring songs to a similar level; it is not a broadcast-certified measure.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

FRAME_S = 0.05
# Frames quieter than this never count as music.
ABSOLUTE_GATE_DB = -60.0
# Frames this far below the song's level are left out of its loudness (quiet intros, fades).
RELATIVE_GATE_DB = 20.0
# The level every song is brought to (dBFS, gated RMS). The catalog's median was -14.7.
TARGET_DB = -16.0
# Turning a song down is free; turning it up is limited so quiet recordings do not clip.
MAX_BOOST_DB = 6.0
MAX_CUT_DB = -12.0
# The music "has ended" once it stays this far below the song's level (a long tail or silence).
TAIL_BELOW_DB = 30.0
SILENCE_FLOOR_DB = -50.0
# Shorter than this between start and end: something is off, so nothing is trimmed.
MIN_MUSIC_S = 10.0


@dataclass(frozen=True)
class Playback:
    gain_db: float
    start_s: float
    end_s: float


def frame_levels(mono: np.ndarray, sample_rate: int) -> np.ndarray:
    """RMS level of each 50 ms frame, in dBFS."""
    hop = max(1, int(sample_rate * FRAME_S))
    count = len(mono) // hop
    if count == 0:
        return np.zeros(0)
    frames = mono[: count * hop].reshape(count, hop).astype(np.float64)
    return 20 * np.log10(np.sqrt((frames**2).mean(axis=1)) + 1e-9)


def gated_loudness(levels: np.ndarray) -> float | None:
    loud = levels[levels > ABSOLUTE_GATE_DB]
    if loud.size == 0:
        return None
    first = 10 * np.log10(np.mean(10 ** (loud / 10)))
    kept = loud[loud > first - RELATIVE_GATE_DB]
    return float(10 * np.log10(np.mean(10 ** (kept / 10))))


def analyse(mono: np.ndarray, sample_rate: int) -> Playback:
    """Gain to the target level, and where the music starts and ends (seconds)."""
    duration = len(mono) / sample_rate
    levels = frame_levels(mono, sample_rate)
    loudness = gated_loudness(levels)
    if loudness is None:  # silent file: play it as it is
        return Playback(gain_db=0.0, start_s=0.0, end_s=round(duration, 2))

    gain = min(MAX_BOOST_DB, max(MAX_CUT_DB, TARGET_DB - loudness))
    threshold = max(SILENCE_FLOOR_DB, loudness - TAIL_BELOW_DB)
    audible = np.flatnonzero(levels > threshold)
    start = audible[0] * FRAME_S
    end = min(duration, (audible[-1] + 1) * FRAME_S)
    if end - start < MIN_MUSIC_S:
        start, end = 0.0, duration
    return Playback(gain_db=round(gain, 1), start_s=round(start, 2), end_s=round(end, 2))


def analyse_file(path: Path) -> Playback:
    """Decode an audio file (MP3 included, through libsndfile) and analyse it."""
    samples, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    return analyse(samples.mean(axis=1), sample_rate)
