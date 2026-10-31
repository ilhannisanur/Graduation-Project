"""Turn any engine's output into the one format the service serves: mono 16-bit WAV."""

from __future__ import annotations

import io
from math import gcd

import numpy as np
import soundfile as sf


def resample(samples: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    if from_rate == to_rate:
        return samples.astype(np.float32, copy=False)
    from scipy.signal import resample_poly

    g = gcd(from_rate, to_rate)
    return resample_poly(samples, to_rate // g, from_rate // g).astype(np.float32)


def to_wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, np.clip(samples, -1.0, 1.0), sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def wav_duration(path) -> float:
    info = sf.info(str(path))
    return info.frames / float(info.samplerate)


def loudness_lufs(samples: np.ndarray, sample_rate: int) -> float | None:
    """Integrated loudness if pyloudnorm is installed (it comes with Chatterbox; optional)."""
    try:
        import pyloudnorm
    except ImportError:
        return None
    if len(samples) < sample_rate * 0.5:
        return None
    value = pyloudnorm.Meter(sample_rate).integrated_loudness(samples.astype(np.float64))
    return round(float(value), 2) if np.isfinite(value) else None
