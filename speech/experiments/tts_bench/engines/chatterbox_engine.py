"""Chatterbox (MIT, Resemble AI).

* ChatterboxEngine: the original 500M model. Emotion is steered with
  ``exaggeration`` and ``cfg_weight`` plus an optional reference clip
  per emotion. The model ships a built-in voice, so refs are optional.
* ChatterboxTurboEngine: the 350M Turbo model. According to its source code
  (chatterbox-tts 0.1.7) Turbo ignores ``exaggeration`` and ``cfg_weight``,
  so emotion can only come from the reference clip and paralinguistic tags
  such as [laugh] / [chuckle].

Generated audio carries Resemble's imperceptible Perth watermark.
"""

from __future__ import annotations

from typing import Any

from .base import Audio, SynthesisRequest, TTSEngine, lerp, to_mono_float32

# Values at intensity 1.0. Neutral is the library default (0.5 / 0.5).
# Starting hypotheses; tune them after listening and record the final values.
EXAGGERATION_FULL = {
    "neutral": 0.5,
    "happy": 0.8,
    "excited": 1.1,
    "calm": 0.3,
    "sad": 0.65,
    "serious": 0.4,
    "surprised": 0.95,
}
CFG_WEIGHT_FULL = {
    "neutral": 0.5,
    "happy": 0.45,
    "excited": 0.3,
    "calm": 0.55,
    "sad": 0.5,
    "serious": 0.55,
    "surprised": 0.4,
}

# Optional Turbo tags (enable with --option tags=true).
TURBO_TAGS = {"happy": "[chuckle]", "excited": "[laugh]"}


def _flag(value: str | None) -> bool:
    return str(value).lower() in {"1", "true", "yes", "on"}


class ChatterboxEngine(TTSEngine):
    name = "chatterbox"

    def load(self) -> None:
        import torch
        from chatterbox.tts import ChatterboxTTS

        self._torch = torch
        self.model = ChatterboxTTS.from_pretrained(device=self.device)
        self._current_ref: str | None = None

    def settings_for(self, req: SynthesisRequest) -> dict[str, Any]:
        ref = self.reference_for(req.emotion)
        return {
            "exaggeration": lerp(0.5, EXAGGERATION_FULL[req.emotion], req.intensity),
            "cfg_weight": lerp(0.5, CFG_WEIGHT_FULL[req.emotion], req.intensity),
            "temperature": float(self.options.get("temperature", 0.8)),
            "reference": ref.name if ref else "built-in voice",
        }

    def synthesize(self, req: SynthesisRequest) -> Audio:
        settings = self.settings_for(req)
        ref = self.reference_for(req.emotion)
        if ref is not None and str(ref) != self._current_ref:
            # Computing the voice embedding is slow, so only redo it when the clip changes.
            self.model.prepare_conditionals(str(ref), exaggeration=settings["exaggeration"])
            self._current_ref = str(ref)

        self._torch.manual_seed(self.seed)
        wav = self.model.generate(
            req.text,
            exaggeration=settings["exaggeration"],
            cfg_weight=settings["cfg_weight"],
            temperature=settings["temperature"],
        )
        return Audio(to_mono_float32(wav), int(self.model.sr))


class ChatterboxTurboEngine(TTSEngine):
    name = "chatterbox-turbo"

    def load(self) -> None:
        import torch
        from chatterbox.tts_turbo import ChatterboxTurboTTS

        self._torch = torch
        self.model = ChatterboxTurboTTS.from_pretrained(device=self.device)
        if self.refs_dir is None and getattr(self.model, "conds", None) is None:
            raise RuntimeError(
                "Chatterbox Turbo has no built-in voice in this checkpoint. "
                "Pass --refs with at least refs/neutral.wav (5-10 s, consented voice)."
            )

    def settings_for(self, req: SynthesisRequest) -> dict[str, Any]:
        ref = self.reference_for(req.emotion)
        tag = ""
        if _flag(self.options.get("tags")) and req.intensity >= 0.5:
            tag = TURBO_TAGS.get(req.emotion, "")
        return {
            "temperature": float(self.options.get("temperature", 0.8)),
            "reference": ref.name if ref else "built-in voice",
            "tag": tag,
        }

    def synthesize(self, req: SynthesisRequest) -> Audio:
        settings = self.settings_for(req)
        ref = self.reference_for(req.emotion)
        text = f"{settings['tag']} {req.text}".strip()
        self._torch.manual_seed(self.seed)
        wav = self.model.generate(
            text,
            audio_prompt_path=str(ref) if ref else None,
            temperature=settings["temperature"],
        )
        return Audio(to_mono_float32(wav), int(self.model.sr))
