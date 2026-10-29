"""Small, dependency-light audio measurements."""

from __future__ import annotations

import numpy as np

SILENCE_DBFS = -45.0


def _dbfs(value: float) -> float:
    return round(20 * np.log10(max(value, 1e-9)), 2)


def peak_dbfs(samples: np.ndarray) -> float:
    return _dbfs(float(np.max(np.abs(samples))) if samples.size else 0.0)


def rms_dbfs(samples: np.ndarray) -> float:
    return _dbfs(float(np.sqrt(np.mean(np.square(samples, dtype=np.float64)))) if samples.size else 0.0)


def edge_silence_sec(samples: np.ndarray, sample_rate: int, frame_ms: int = 20) -> tuple[float, float]:
    """Leading and trailing silence. Long silences break the radio flow."""
    frame = max(1, sample_rate * frame_ms // 1000)
    n = len(samples) // frame
    if n == 0:
        return 0.0, 0.0
    frames = samples[: n * frame].reshape(n, frame).astype(np.float64)
    loud = 20 * np.log10(np.sqrt(np.mean(frames**2, axis=1)) + 1e-9) > SILENCE_DBFS
    if not loud.any():
        total = round(len(samples) / sample_rate, 3)
        return total, total
    first = int(np.argmax(loud))
    last = int(n - 1 - np.argmax(loud[::-1]))
    to_sec = frame / sample_rate
    return round(first * to_sec, 3), round((n - 1 - last) * to_sec, 3)


def loudness_lufs(samples: np.ndarray, sample_rate: int) -> float | None:
    """Integrated loudness if pyloudnorm is installed (Chatterbox brings it)."""
    try:
        import pyloudnorm
    except ImportError:
        return None
    if len(samples) < sample_rate * 0.5:
        return None
    value = pyloudnorm.Meter(sample_rate).integrated_loudness(samples.astype(np.float64))
    return round(float(value), 2) if np.isfinite(value) else None
