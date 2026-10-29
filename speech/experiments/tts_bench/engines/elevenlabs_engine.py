"""ElevenLabs (commercial cloud API) - used as a quality reference.

Plain HTTPS with the standard library, so it runs in any of the virtual
environments and needs no SDK. Settings are read from the environment or from
a ``.env`` file next to pyproject.toml (never commit it)::

    ELEVENLABS_API_KEY=sk_...
    ELEVENLABS_VOICE_ID=...      # optional; pick one with: python -m tts_bench.elevenlabs_tools voices

Emotion handles:
* ``eleven_v3`` (default): free-form audio tags in square brackets, e.g.
  [excited], [sad]. ``stability`` must be 0.0 (creative), 0.5 (natural) or
  1.0 (robust) on v3.
* other models (``eleven_multilingual_v2``...): no tags; ``style`` and a lower
  ``stability`` make the delivery more expressive.

Only the fixed test sentences are sent. Never send listener data to this API.
"""

from __future__ import annotations

import io
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

from .base import Audio, SynthesisRequest, TTSEngine, lerp

API_BASE = "https://api.elevenlabs.io"
TTS_PATH = "/v1/text-to-speech/{voice_id}?output_format={fmt}"
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # premade voice used in the official API examples
DEFAULT_MODEL = "eleven_v3"
PCM_RATE = 24_000
FALLBACK_FORMAT = "mp3_44100_128"  # available on every plan

# eleven_v3 audio tags used when intensity >= 0.5
V3_TAGS = {
    "happy": "[cheerfully]",
    "excited": "[excited]",
    "calm": "[calmly]",
    "sad": "[sad]",
    "serious": "[seriously]",
    "surprised": "[surprised]",
}
# style (0..1) at intensity 1.0 for models without tags
STYLE_FULL = {
    "neutral": 0.0,
    "happy": 0.5,
    "excited": 0.8,
    "calm": 0.2,
    "sad": 0.5,
    "serious": 0.3,
    "surprised": 0.7,
}


def load_env_value(name: str, start: Path | None = None) -> str | None:
    """A setting from the environment, or from the nearest .env file upwards."""
    if os.environ.get(name):
        return os.environ[name].strip()
    here = (start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        env_file = folder / ".env"
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                key, sep, value = line.partition("=")
                if sep and key.strip() == name:
                    return value.strip().strip('"').strip("'") or None
            return None  # the nearest .env decides
    return None


def load_api_key(start: Path | None = None) -> str | None:
    return load_env_value("ELEVENLABS_API_KEY", start)


class ElevenLabsError(RuntimeError):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"ElevenLabs HTTP {status}: {detail}\n{explain_error(status, detail)}".rstrip())


def explain_error(status: int, detail: str) -> str:
    """A hint in plain words for the errors people actually hit."""
    text = detail.lower()
    if status == 401:
        return "Hint: the API key is wrong, or it has no 'Text to Speech' permission (ElevenLabs > API Keys)."
    if "quota" in text or "credits" in text or status == 402:
        return "Hint: the monthly character quota is used up. Check it: python -m tts_bench.elevenlabs_tools check"
    if "voice" in text and status in (400, 404, 422):
        return "Hint: this voice is not available. List voices: python -m tts_bench.elevenlabs_tools voices"
    if "model" in text and status in (400, 403, 422):
        return "Hint: this model is not available on your plan. Try: --option model=eleven_multilingual_v2"
    return ""


def _is_format_problem(status: int, detail: str) -> bool:
    text = detail.lower()
    return status in (400, 403, 422) and ("format" in text or "pcm" in text or "tier" in text)


class ElevenLabsEngine(TTSEngine):
    name = "elevenlabs"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.model_id = self.options.get("model", DEFAULT_MODEL)
        self.voice_id = self.options.get("voice_id") or load_env_value("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE_ID
        self.fmt = self.options.get("format", f"pcm_{PCM_RATE}")
        self.api_key: str | None = None

    def load(self) -> None:
        self.api_key = load_api_key()
        if not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY not found. Put it in speech/experiments/.env (never commit it).")

    @property
    def _is_v3(self) -> bool:
        return self.model_id.startswith("eleven_v3")

    def settings_for(self, req: SynthesisRequest) -> dict[str, Any]:
        settings: dict[str, Any] = {"model": self.model_id, "voice_id": self.voice_id}
        if self._is_v3:
            tag = V3_TAGS.get(req.emotion, "") if req.intensity >= 0.5 else ""
            settings["text"] = f"{tag} {req.text}".strip()
            settings["voice_settings"] = {"stability": float(self.options.get("stability", 0.5))}
        else:
            settings["text"] = req.text
            settings["voice_settings"] = {
                "stability": lerp(0.5, 0.3, req.intensity) if req.emotion != "neutral" else 0.5,
                "similarity_boost": 0.75,
                "style": lerp(0.0, STYLE_FULL[req.emotion], req.intensity),
            }
        return settings

    def build_request(self, req: SynthesisRequest) -> urllib.request.Request:
        s = self.settings_for(req)
        body = {"text": s["text"], "model_id": s["model"], "voice_settings": s["voice_settings"], "seed": self.seed}
        return urllib.request.Request(
            API_BASE + TTS_PATH.format(voice_id=s["voice_id"], fmt=self.fmt),
            data=json.dumps(body).encode("utf-8"),
            headers={"xi-api-key": self.api_key or "", "Content-Type": "application/json", "Accept": "audio/*"},
            method="POST",
        )

    def _post(self, request: urllib.request.Request) -> bytes:
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=120) as resp:
                    return resp.read()
            except urllib.error.HTTPError as err:
                detail = err.read().decode("utf-8", "replace")[:300]
                if err.code == 429 and attempt < 2:  # rate limited: wait and retry
                    time.sleep(5 * (attempt + 1))
                    continue
                raise ElevenLabsError(err.code, detail) from None
        raise RuntimeError("ElevenLabs: too many retries")

    def synthesize(self, req: SynthesisRequest) -> Audio:
        try:
            data = self._post(self.build_request(req))
        except ElevenLabsError as err:
            if not (self.fmt.startswith("pcm_") and _is_format_problem(err.status, err.detail)):
                raise
            # some plans do not offer raw PCM: switch to MP3 once and keep using it
            print(f"ElevenLabs: {self.fmt} not available, switching to {FALLBACK_FORMAT}")
            self.fmt = FALLBACK_FORMAT
            data = self._post(self.build_request(req))
        return self._decode(data)

    def _decode(self, data: bytes) -> Audio:
        if self.fmt.startswith("pcm_"):
            rate = int(self.fmt.split("_")[1])
            pcm = np.frombuffer(data, dtype="<i2")
            return Audio(pcm.astype(np.float32) / 32768.0, rate)
        import soundfile as sf  # mp3 decoding needs libsndfile >= 1.1 (soundfile >= 0.12)

        samples, rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=False)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        return Audio(samples, int(rate))
