"""Engine registry with lazy imports, so a missing model package only
fails when that engine is actually used."""

from __future__ import annotations

import importlib

from .base import EMOTIONS, Audio, SynthesisRequest, TTSEngine

_REGISTRY: dict[str, str] = {
    "kokoro": "tts_bench.engines.kokoro_engine:KokoroEngine",
    "chatterbox": "tts_bench.engines.chatterbox_engine:ChatterboxEngine",
    "chatterbox-turbo": "tts_bench.engines.chatterbox_engine:ChatterboxTurboEngine",
    "styletts2": "tts_bench.engines.styletts2_engine:StyleTTS2Engine",
    "orpheus": "tts_bench.engines.orpheus_engine:OrpheusEngine",
    "orpheus-hf": "tts_bench.engines.orpheus_engine:OrpheusHFEngine",
    "elevenlabs": "tts_bench.engines.elevenlabs_engine:ElevenLabsEngine",
}


def available_engines() -> list[str]:
    return sorted(_REGISTRY)


def register(name: str, target: str | type[TTSEngine]) -> None:
    """Register an engine class or a 'module:Class' path."""
    _REGISTRY[name] = target  # type: ignore[assignment]


def get_engine_class(name: str) -> type[TTSEngine]:
    try:
        target = _REGISTRY[name]
    except KeyError:
        raise ValueError(f"Unknown engine {name!r}; available: {available_engines()}") from None
    if isinstance(target, type):
        return target
    module_name, class_name = target.split(":")
    return getattr(importlib.import_module(module_name), class_name)


def create_engine(name: str, **kwargs) -> TTSEngine:
    return get_engine_class(name)(**kwargs)


__all__ = [
    "EMOTIONS",
    "Audio",
    "SynthesisRequest",
    "TTSEngine",
    "available_engines",
    "create_engine",
    "get_engine_class",
    "register",
]
