"""Engine selection, fallback and the content-addressed audio cache.

The engines come from ``tts_bench.engines`` (speech/experiments), the same
code that was measured in #4, so the service and the comparison never drift
apart. Changing the model is a setting (TTS_ENGINE), not a code change.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tts_bench.engines import create_engine
from tts_bench.engines.base import SynthesisRequest, TTSEngine

from . import audio
from .config import Settings

logger = logging.getLogger("speech_service")

CACHE_VERSION = 1  # bump to invalidate every cached file after an output-format change
GPU_ONLY_ENGINES = {"orpheus", "orpheus-hf", "indextts2", "qwen3-tts"}
DEFAULT_GPU_ENGINE = "orpheus-hf"
DEFAULT_CPU_ENGINE = "kokoro"

EngineFactory = Callable[..., TTSEngine]


class SynthesisFailed(RuntimeError):
    pass


@dataclass
class SynthesisResult:
    file: Path
    duration_s: float
    sample_rate: int
    engine: str
    cached: bool
    loudness_lufs: float | None = None


def cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available())


class _Slot:
    """One engine with its own lock (engines are not thread-safe)."""

    def __init__(self, name: str, device: str, options: dict[str, str], factory: EngineFactory) -> None:
        self.name = name
        self.device = device
        self.options = options
        self._factory = factory
        self._engine: TTSEngine | None = None
        self._lock = threading.Lock()
        self.error: str | None = None

    @property
    def ready(self) -> bool:
        return self._engine is not None

    def load(self) -> None:
        with self._lock:
            if self._engine is not None:
                return
            try:
                engine = self._factory(self.name, device=self.device, **self.options)
                engine.load()
            except Exception as exc:
                self.error = f"{type(exc).__name__}: {exc}"[:300]
                raise
            self._engine, self.error = engine, None
            logger.info("engine %s loaded on %s", self.name, self.device)

    def synthesize(self, req: SynthesisRequest):
        self.load()
        with self._lock:
            assert self._engine is not None
            return self._engine.synthesize(req)


class Synthesizer:
    def __init__(self, settings: Settings, factory: EngineFactory = create_engine, gpu: bool | None = None) -> None:
        self.settings = settings
        gpu = cuda_available() if gpu is None else gpu
        if settings.device == "auto":
            self.device = "cuda" if gpu else "cpu"
        else:
            self.device = settings.device
        self.notes: list[str] = []

        name = settings.engine
        if name == "auto":
            name = DEFAULT_GPU_ENGINE if self.device == "cuda" else DEFAULT_CPU_ENGINE
        self.primary: _Slot | None = None
        if name in GPU_ONLY_ENGINES and self.device != "cuda":
            self.notes.append(f"{name} needs a CUDA GPU; none found, so only the fallback engine is used")
            logger.warning(self.notes[-1])
        else:
            self.primary = _Slot(name, self.device, settings.engine_options, factory)

        self.fallback: _Slot | None = None
        fb = settings.fallback_engine
        if fb and (self.primary is None or fb != self.primary.name):
            # the fallback must work without a GPU, so it always runs on the CPU
            self.fallback = _Slot(fb, "cpu", settings.fallback_options, factory)
        if self.primary is None and self.fallback is None:
            raise SynthesisFailed("no usable engine: set TTS_ENGINE or TTS_FALLBACK_ENGINE")

        settings.audio_dir.mkdir(parents=True, exist_ok=True)
        self._inflight: dict[str, asyncio.Future] = {}

    # --- info ---------------------------------------------------------------------

    def status(self) -> dict:
        def slot(s: _Slot | None) -> dict | None:
            if s is None:
                return None
            return {"engine": s.name, "device": s.device, "ready": s.ready, "error": s.error}

        primary_ok = self.primary is not None and self.primary.error is None
        return {
            "status": "ok" if primary_ok else "degraded",
            "primary": slot(self.primary),
            "fallback": slot(self.fallback),
            "sample_rate": self.settings.sample_rate,
            "notes": self.notes,
        }

    def load(self) -> None:
        """Load the engines now (at startup) instead of on the first request."""
        for s in (self.primary, self.fallback):
            if s is None:
                continue
            try:
                s.load()
            except Exception:
                logger.exception("could not load engine %s", s.name)

    # --- cache ----------------------------------------------------------------------

    def cache_key(self, slot: _Slot, req: SynthesisRequest, voice_id: str | None) -> str:
        payload = {
            "v": CACHE_VERSION,
            "engine": slot.name,
            "options": slot.options,
            "voice": voice_id or "default",
            "emotion": req.emotion,
            "intensity": round(req.intensity, 2),
            "text": req.text,
            "rate": self.settings.sample_rate,
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        return digest.hexdigest()[:32]

    def path_for(self, key: str) -> Path:
        return self.settings.audio_dir / f"{key}.wav"

    def _cached(self, key: str, slot: _Slot) -> SynthesisResult | None:
        path = self.path_for(key)
        if not path.is_file():
            return None
        return SynthesisResult(path, round(audio.wav_duration(path), 3), self.settings.sample_rate, slot.name, True)

    # --- synthesis -------------------------------------------------------------------

    def _render(self, slot: _Slot, req: SynthesisRequest, key: str) -> SynthesisResult:
        out = slot.synthesize(req)
        if out.duration_sec <= 0:
            raise SynthesisFailed(f"{slot.name} returned empty audio")
        samples = audio.resample(out.samples, out.sample_rate, self.settings.sample_rate)
        path = self.path_for(key)
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_bytes(audio.to_wav_bytes(samples, self.settings.sample_rate))
        tmp.replace(path)  # atomic: a reader never sees a half-written file
        return SynthesisResult(
            path,
            round(len(samples) / self.settings.sample_rate, 3),
            self.settings.sample_rate,
            slot.name,
            False,
            audio.loudness_lufs(samples, self.settings.sample_rate),
        )

    async def _once(self, key: str, make):
        """Identical requests that arrive together share one synthesis."""
        if key in self._inflight:
            return await asyncio.shield(self._inflight[key])
        future = asyncio.get_running_loop().create_future()
        self._inflight[key] = future
        try:
            result = await make()
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            future.exception()  # mark as retrieved
            raise
        finally:
            del self._inflight[key]

    async def synthesize(self, req: SynthesisRequest, voice_id: str | None = None) -> SynthesisResult:
        errors: list[str] = []
        for slot in (self.primary, self.fallback):
            if slot is None:
                continue
            key = self.cache_key(slot, req, voice_id)
            hit = self._cached(key, slot)
            if hit is not None:
                return hit
            try:
                return await self._once(key, lambda s=slot, k=key: asyncio.to_thread(self._render, s, req, k))
            except Exception as exc:
                errors.append(f"{slot.name}: {type(exc).__name__}: {exc}"[:300])
                logger.warning("engine %s failed: %s", slot.name, errors[-1])
        raise SynthesisFailed("; ".join(errors) or "no engine available")
