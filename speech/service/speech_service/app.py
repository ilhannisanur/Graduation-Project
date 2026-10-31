"""HTTP API of the speech service (#8).

    POST /synthesize        {"text", "emotion", "intensity", "voice_id"} -> audio file info
    GET  /audio/{name}.wav  the generated audio (cached by content)
    GET  /health            which engine runs where, and whether it is ready

Run (from speech/service):  .venv/bin/uvicorn speech_service.app:app --port 8001
"""

from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from tts_bench.engines.base import EMOTIONS, SynthesisRequest

from .config import Settings
from .synthesizer import SynthesisFailed, Synthesizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

Emotion = Literal["neutral", "happy", "excited", "calm", "sad", "serious", "surprised"]
assert set(Emotion.__args__) == set(EMOTIONS), "keep the API emotions equal to tts_bench EMOTIONS"
VOICES = {"default"}  # role names (e.g. host_female_1) come with the presenter work (#5)
_FILE_RE = re.compile(r"^[0-9a-f]{32}\.wav$")


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1)
    emotion: Emotion = "neutral"
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    voice_id: str | None = None
    target_duration_s: float | None = Field(default=None, gt=0)  # accepted, not used yet (#22)

    @field_validator("text")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("text is empty")
        return value


class SynthesizeResponse(BaseModel):
    audio_url: str
    duration_s: float
    sample_rate: int
    engine: str
    cached: bool
    loudness_lufs: float | None = None


def create_app(settings: Settings | None = None, synthesizer: Synthesizer | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.synth = synthesizer or Synthesizer(settings)
        if settings.load_on_startup:
            app.state.synth.load()
        yield

    app = FastAPI(title="Speech service", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict:
        return app.state.synth.status()

    @app.post("/synthesize", response_model=SynthesizeResponse)
    async def synthesize(body: SynthesizeRequest) -> SynthesizeResponse:
        if len(body.text) > settings.max_text_chars:
            raise HTTPException(
                422,
                f"text is longer than {settings.max_text_chars} characters",
            )
        if body.voice_id is not None and body.voice_id not in VOICES:
            raise HTTPException(422, f"unknown voice_id {body.voice_id!r}")
        req = SynthesisRequest(text=body.text, emotion=body.emotion, intensity=body.intensity)
        try:
            result = await app.state.synth.synthesize(req, body.voice_id)
        except SynthesisFailed as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"speech synthesis failed: {exc}") from exc
        return SynthesizeResponse(
            audio_url=f"/audio/{result.file.name}",
            duration_s=result.duration_s,
            sample_rate=result.sample_rate,
            engine=result.engine,
            cached=result.cached,
            loudness_lufs=result.loudness_lufs,
        )

    @app.get("/audio/{name}")
    def get_audio(name: str) -> FileResponse:
        path = settings.audio_dir / name
        if not _FILE_RE.match(name) or not path.is_file():  # the name check also blocks "../" paths
            raise HTTPException(status.HTTP_404_NOT_FOUND, "audio not found")
        return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "public, max-age=31536000"})

    return app


def __getattr__(name: str):
    # `uvicorn speech_service.app:app` builds the app on first access, so importing
    # this module (e.g. in tests) does not read .env or load a model
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
