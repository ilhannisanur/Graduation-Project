"""Settings of the speech service, read from environment variables or speech/service/.env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent  # speech/service


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _options(raw: str) -> dict[str, str]:
    """'voice=af_heart,speed=1' -> {'voice': 'af_heart', 'speed': '1'}"""
    out: dict[str, str] = {}
    for part in filter(None, (p.strip() for p in raw.split(","))):
        if "=" not in part:
            raise ValueError(f"engine option must be key=value, got {part!r}")
        key, value = part.split("=", 1)
        out[key.strip()] = value.strip()
    return out


@dataclass
class Settings:
    # "auto": Orpheus on a CUDA GPU, otherwise Kokoro on the CPU
    engine: str = "auto"
    fallback_engine: str = "kokoro"  # "" disables the fallback
    device: str = "auto"  # auto, cpu or cuda
    engine_options: dict[str, str] = field(default_factory=dict)
    fallback_options: dict[str, str] = field(default_factory=dict)
    audio_dir: Path = SERVICE_DIR / "data" / "audio"
    sample_rate: int = 24_000  # every engine's output is converted to this
    max_text_chars: int = 1_000
    load_on_startup: bool = True

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> Settings:
        values = _read_env_file(env_file or SERVICE_DIR / ".env")
        values.update({k: v for k, v in os.environ.items() if k.startswith("TTS_") or k.startswith("SPEECH_")})

        def get(key: str, default: str) -> str:
            return values.get(key, default)

        audio_dir = Path(get("SPEECH_AUDIO_DIR", str(cls.audio_dir)))
        if not audio_dir.is_absolute():
            audio_dir = SERVICE_DIR / audio_dir
        return cls(
            engine=get("TTS_ENGINE", "auto"),
            fallback_engine=get("TTS_FALLBACK_ENGINE", "kokoro"),
            device=get("TTS_DEVICE", "auto"),
            engine_options=_options(get("TTS_ENGINE_OPTIONS", "")),
            fallback_options=_options(get("TTS_FALLBACK_OPTIONS", "")),
            audio_dir=audio_dir,
            sample_rate=int(get("SPEECH_SAMPLE_RATE", "24000")),
            max_text_chars=int(get("SPEECH_MAX_TEXT_CHARS", "1000")),
            load_on_startup=get("SPEECH_LOAD_ON_STARTUP", "true").lower() in {"1", "true", "yes"},
        )
