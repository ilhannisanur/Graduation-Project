"""Orpheus 3B (Canopy Labs). GPU only: on CPU it is far slower than real time.

Emotion handles: emotive tags (<laugh>, <chuckle>, <sigh>, <gasp>...) placed in
the text, plus the speaker voice. There is no numeric emotion knob.

Two backends:
* ``orpheus-hf`` (recommended on Colab): plain transformers + the SNAC decoder.
  Slower than vLLM but has no fragile dependency pins.
* ``orpheus``: the official ``orpheus-speech`` package on vLLM (Linux + GPU).
  Patched to use float16 and a short ``max_model_len`` so it fits on a free T4.

The model repo is gated: accept the licence on Hugging Face and log in first.
"""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np

from .base import Audio, SynthesisRequest, TTSEngine

HF_MODEL_ID = "canopylabs/orpheus-3b-0.1-ft"
VLLM_MODEL_ID = "canopylabs/orpheus-tts-0.1-finetune-prod"
SNAC_MODEL_ID = "hubertsiuzdak/snac_24khz"
SAMPLE_RATE = 24_000

# Special token ids of the Orpheus tokenizer (from orpheus-speech 0.1.0).
START_OF_HUMAN = 128259
END_OF_TEXT = 128009
END_OF_HUMAN = 128260
START_OF_AI = 128261
START_OF_SPEECH = 128257
END_OF_SPEECH = 128258
AUDIO_TOKEN_OFFSET = 128266  # first SNAC code token
CODEBOOK_SIZE = 4096

# (tag, position) used when intensity >= 0.5
EMOTION_TAGS = {
    "happy": ("<chuckle>", "end_of_first_sentence"),
    "excited": ("<laugh>", "start"),
    "sad": ("<sigh>", "start"),
    "surprised": ("<gasp>", "start"),
}


def apply_tag(text: str, emotion: str, intensity: float) -> str:
    if intensity < 0.5 or emotion not in EMOTION_TAGS:
        return text
    tag, position = EMOTION_TAGS[emotion]
    if position == "start":
        return f"{tag} {text}"
    for mark in (". ", "! ", "? ", ", "):
        idx = text.find(mark)
        if idx != -1:
            return f"{text[: idx + 1]} {tag}{text[idx + 1 :]}"
    return f"{text} {tag}"


def tokens_to_snac_layers(token_ids: list[int]) -> tuple[list[int], list[int], list[int]]:
    """Turn generated audio tokens into the three SNAC codebook layers.

    Every 7 tokens form one frame laid out as [L1, L2, L3, L3, L2, L3, L3];
    token i of a frame is shifted by i * 4096 on top of the global offset.
    """
    codes = [t - AUDIO_TOKEN_OFFSET for t in token_ids if t >= AUDIO_TOKEN_OFFSET]
    frames = len(codes) // 7
    layer1: list[int] = []
    layer2: list[int] = []
    layer3: list[int] = []
    for f in range(frames):
        c = [codes[7 * f + i] - i * CODEBOOK_SIZE for i in range(7)]
        if any(not 0 <= v < CODEBOOK_SIZE for v in c):
            continue  # a malformed frame; skipping it is what the official decoder does
        layer1.append(c[0])
        layer2.extend((c[1], c[4]))
        layer3.extend((c[2], c[3], c[5], c[6]))
    return layer1, layer2, layer3


class _OrpheusBase(TTSEngine):
    def settings_for(self, req: SynthesisRequest) -> dict[str, Any]:
        return {
            "voice": self.options.get("voice", "tara"),
            "prompt": apply_tag(req.text, req.emotion, req.intensity),
            "temperature": float(self.options.get("temperature", 0.6)),
            "top_p": float(self.options.get("top_p", 0.95)),
            "repetition_penalty": float(self.options.get("repetition_penalty", 1.1)),
        }


class OrpheusHFEngine(_OrpheusBase):
    name = "orpheus-hf"

    def load(self) -> None:
        import torch
        from snac import SNAC
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._torch = torch
        model_id = self.options.get("model", HF_MODEL_ID)
        if self.device == "cuda":
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        else:
            dtype = torch.float32
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=dtype).to(self.device).eval()
        self.snac = SNAC.from_pretrained(SNAC_MODEL_ID).eval().to(self.device)

    def synthesize(self, req: SynthesisRequest) -> Audio:
        torch = self._torch
        s = self.settings_for(req)
        text_ids = self.tokenizer(f"{s['voice']}: {s['prompt']}", return_tensors="pt").input_ids
        input_ids = torch.cat(
            [
                torch.tensor([[START_OF_HUMAN]]),
                text_ids,
                torch.tensor([[END_OF_TEXT, END_OF_HUMAN, START_OF_AI, START_OF_SPEECH]]),
            ],
            dim=1,
        ).to(self.device)
        torch.manual_seed(self.seed)
        with torch.inference_mode():
            out = self.model.generate(
                input_ids=input_ids,
                attention_mask=torch.ones_like(input_ids),
                max_new_tokens=int(self.options.get("max_new_tokens", 1500)),
                do_sample=True,
                temperature=s["temperature"],
                top_p=s["top_p"],
                repetition_penalty=s["repetition_penalty"],
                eos_token_id=END_OF_SPEECH,
            )
        generated = out[0, input_ids.shape[1] :].tolist()
        layers = tokens_to_snac_layers(generated)
        if not layers[0]:
            raise RuntimeError("Orpheus produced no audio tokens")
        codes = [torch.tensor(layer, dtype=torch.int32, device=self.device).unsqueeze(0) for layer in layers]
        with torch.inference_mode():
            wav = self.snac.decode(codes)
        return Audio(wav.squeeze().float().cpu().numpy(), SAMPLE_RATE)


class OrpheusEngine(_OrpheusBase):
    name = "orpheus"

    def load(self) -> None:
        import torch
        from orpheus_tts import OrpheusModel
        from vllm import AsyncEngineArgs, AsyncLLMEngine

        max_len = int(self.options.get("max_model_len", 2048))
        gpu_util = float(self.options.get("gpu_memory_utilization", 0.85))

        class _T4OrpheusModel(OrpheusModel):
            def _setup_engine(inner):  # noqa: N805 - mirrors the parent signature
                args = AsyncEngineArgs(
                    model=inner.model_name,
                    dtype=inner.dtype,
                    max_model_len=max_len,
                    gpu_memory_utilization=gpu_util,
                )
                return AsyncLLMEngine.from_engine_args(args)

        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        self.model = _T4OrpheusModel(model_name=self.options.get("model", VLLM_MODEL_ID), dtype=dtype)

    def synthesize(self, req: SynthesisRequest) -> Audio:
        s = self.settings_for(req)
        chunks = self.model.generate_speech(
            prompt=s["prompt"],
            voice=s["voice"],
            request_id=f"bench-{uuid.uuid4().hex[:8]}",
            temperature=s["temperature"],
            top_p=s["top_p"],
            repetition_penalty=s["repetition_penalty"],
        )
        pcm = np.frombuffer(b"".join(chunks), dtype=np.int16)
        return Audio(pcm.astype(np.float32) / 32768.0, SAMPLE_RATE)
