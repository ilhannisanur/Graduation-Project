"""StyleTTS2 via the `styletts2` pip package (LibriTTS checkpoint).

Emotion handles:
* ``embedding_scale``: higher = style follows the text more = more emotional.
* ``beta``: lower = prosody follows the reference clip more.
* an optional reference clip per emotion.

It runs on CPU, but install it in its own virtual environment: its pinned
dependencies (old transformers / huggingface-hub) conflict with the other engines.
"""

from __future__ import annotations

from typing import Any

from .base import Audio, SynthesisRequest, TTSEngine, lerp, to_mono_float32

EMBEDDING_SCALE_FULL = {
    "neutral": 1.0,
    "happy": 1.8,
    "excited": 2.2,
    "calm": 1.2,
    "sad": 1.8,
    "serious": 1.3,
    "surprised": 2.0,
}
SAMPLE_RATE = 24_000


class StyleTTS2Engine(TTSEngine):
    name = "styletts2"

    def load(self) -> None:
        import numpy as np
        import torch
        from styletts2 import tts

        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        self.model = tts.StyleTTS2()

    def settings_for(self, req: SynthesisRequest) -> dict[str, Any]:
        ref = self.reference_for(req.emotion)
        return {
            "embedding_scale": lerp(1.0, EMBEDDING_SCALE_FULL[req.emotion], req.intensity),
            "alpha": 0.3,
            "beta": 0.4 if ref else 0.7,
            "diffusion_steps": int(self.options.get("diffusion_steps", 10)),
            "reference": ref.name if ref else "default voice",
        }

    def synthesize(self, req: SynthesisRequest) -> Audio:
        settings = self.settings_for(req)
        ref = self.reference_for(req.emotion)
        out = self.model.inference(
            req.text,
            target_voice_path=str(ref) if ref else None,
            output_sample_rate=SAMPLE_RATE,
            alpha=settings["alpha"],
            beta=settings["beta"],
            diffusion_steps=settings["diffusion_steps"],
            embedding_scale=settings["embedding_scale"],
        )
        return Audio(to_mono_float32(out), SAMPLE_RATE)
