"""Kokoro-82M (Apache-2.0). Fast on CPU, but it has no emotion input:
we can only change the speaking speed and the voice. That limitation is
itself a result for the report."""

from __future__ import annotations

from typing import Any

import numpy as np

from .base import Audio, SynthesisRequest, TTSEngine, lerp, to_mono_float32

# Speed at intensity 1.0; neutral is 1.0.
SPEED_FULL = {
    "neutral": 1.0,
    "happy": 1.02,
    "excited": 1.04,
    "calm": 0.96,
    "sad": 0.95,
    "serious": 0.97,
    "surprised": 1.03,
}
SAMPLE_RATE = 24_000


class KokoroEngine(TTSEngine):
    name = "kokoro"

    def load(self) -> None:
        from kokoro import KPipeline

        self.voice = self.options.get("voice", "af_heart")
        # 'a' = American English, 'b' = British English
        self.pipeline = KPipeline(
            lang_code=self.options.get("lang", "a"), repo_id="hexgrad/Kokoro-82M", device=self.device
        )

    def settings_for(self, req: SynthesisRequest) -> dict[str, Any]:
        return {
            "voice": self.options.get("voice", "af_heart"),
            # "speed" option: base speaking rate (e.g. 0.9 = 10% slower for every emotion);
            # the emotion still changes it on top of that.
            "speed": float(self.options.get("speed", 1.0))
            * lerp(1.0, SPEED_FULL[req.emotion], req.intensity),
        }

    def synthesize(self, req: SynthesisRequest) -> Audio:
        settings = self.settings_for(req)
        chunks = [
            to_mono_float32(result.audio)
            for result in self.pipeline(req.text, voice=settings["voice"], speed=settings["speed"])
            if result.audio is not None
        ]
        if not chunks:
            raise RuntimeError("Kokoro returned no audio")
        return Audio(np.concatenate(chunks), SAMPLE_RATE)
