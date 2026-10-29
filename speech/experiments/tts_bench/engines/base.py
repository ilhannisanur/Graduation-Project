"""Common interface that every TTS engine in the benchmark implements.

The same interface is meant to be reused by the speech service in S2 (#8),
so engines here should stay free of benchmark-specific code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

# The 7 emotions of issue #4. Keep this list identical to the emotion labels in
# the shared data contract (DJ Brain decides them); test_set.json and the
# per-engine mapping tables must use the same names.
EMOTIONS: tuple[str, ...] = ("neutral", "happy", "excited", "calm", "sad", "serious", "surprised")


@dataclass(frozen=True)
class SynthesisRequest:
    text: str
    emotion: str = "neutral"
    intensity: float = 0.5  # 0.0 = flat, 1.0 = strongest

    def __post_init__(self) -> None:
        if self.emotion not in EMOTIONS:
            raise ValueError(f"Unknown emotion {self.emotion!r}; expected one of {EMOTIONS}")
        if not 0.0 <= self.intensity <= 1.0:
            raise ValueError(f"intensity must be between 0 and 1, got {self.intensity}")


@dataclass
class Audio:
    samples: np.ndarray  # mono float32 in [-1, 1]
    sample_rate: int

    @property
    def duration_sec(self) -> float:
        return len(self.samples) / float(self.sample_rate)


def lerp(neutral: float, full: float, intensity: float) -> float:
    """Move from the neutral setting towards the full-emotion setting."""
    return round(neutral + (full - neutral) * intensity, 4)


def to_mono_float32(samples: Any) -> np.ndarray:
    """Convert torch tensors / int16 arrays / 2-D arrays to mono float32."""
    if hasattr(samples, "detach"):  # torch.Tensor without importing torch
        samples = samples.detach().cpu().numpy()
    arr = np.asarray(samples)
    if arr.dtype == np.int16:
        arr = arr.astype(np.float32) / 32768.0
    arr = arr.astype(np.float32, copy=False)
    if arr.ndim > 1:
        arr = arr.reshape(-1) if 1 in arr.shape else arr.mean(axis=0)
    return arr


class TTSEngine(ABC):
    """Base class for all engines.

    Subclasses keep heavy imports (torch, kokoro, chatterbox...) inside ``load``
    so the benchmark tools and tests can import this package without them.
    """

    name: str = "base"

    def __init__(
        self,
        device: str = "cpu",
        refs_dir: str | Path | None = None,
        seed: int = 42,
        **options: str,
    ) -> None:
        self.device = device
        self.refs_dir = Path(refs_dir) if refs_dir else None
        self.seed = seed
        self.options = options

    def reference_for(self, emotion: str) -> Path | None:
        """refs/<emotion>.wav, falling back to refs/neutral.wav."""
        if self.refs_dir is None:
            return None
        for candidate in (emotion, "neutral"):
            path = self.refs_dir / f"{candidate}.wav"
            if path.exists():
                return path
        return None

    @abstractmethod
    def load(self) -> None:
        """Download/load model weights. Called once, timed separately."""

    @abstractmethod
    def settings_for(self, req: SynthesisRequest) -> dict[str, Any]:
        """The engine parameters used to express this emotion.

        Recorded in metrics.csv so the report can explain how each engine
        was steered.
        """

    @abstractmethod
    def synthesize(self, req: SynthesisRequest) -> Audio:
        """Generate speech for one request."""

    def info(self) -> dict[str, Any]:
        return {"engine": self.name, "device": self.device, "options": self.options}
