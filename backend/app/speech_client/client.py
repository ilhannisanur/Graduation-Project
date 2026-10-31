"""Backend side of the speech service (#8).

The backend never loads a TTS model itself: the model runs in the separate
speech service (speech/service, its own Python environment, port 8001), and
the backend talks to it only through ``SpeechClient``. Tests use a fake
``SpeechClient``, so they need neither the service nor a model.
"""

from __future__ import annotations

from typing import Literal, Protocol, get_args
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, Field

from app.core.config import get_settings

# Same seven labels as the speech service and DJ Brain (docs/tts-karsilastirma.md).
Emotion = Literal["neutral", "happy", "excited", "calm", "sad", "serious", "surprised"]
EMOTIONS: frozenset[str] = frozenset(get_args(Emotion))

DEFAULT_SPEECH_URL = "http://localhost:8001"
# The service answers "/audio/<name>.wav"; the backend serves it as /api/speech/audio/<name>.wav
PUBLIC_AUDIO_BASE = "/api/speech/"


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1)
    emotion: Emotion = "neutral"
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    voice_id: str | None = None
    target_duration_s: float | None = Field(default=None, gt=0)


class SpeechResult(BaseModel):
    audio_url: str  # absolute URL the browser can play
    duration_s: float
    sample_rate: int
    engine: str
    cached: bool = False


class SpeechServiceError(Exception):
    """The speech service is down, rejected the request, or could not synthesize."""


class SpeechClient(Protocol):
    async def synthesize(self, request: SpeechRequest) -> SpeechResult: ...

    async def health(self) -> dict: ...


class HttpSpeechClient:
    """Talks to the speech service over HTTP."""

    def __init__(
        self,
        base_url: str = DEFAULT_SPEECH_URL,
        public_base_url: str | None = None,
        timeout_s: float = 120.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        # where the browser reaches the audio (differs from base_url behind a proxy)
        self.public_base_url = (public_base_url or base_url).rstrip("/") + "/"
        self._client = client or httpx.AsyncClient(timeout=timeout_s)

    async def synthesize(self, request: SpeechRequest) -> SpeechResult:
        data = await self._call("POST", "/synthesize", json=request.model_dump())
        data["audio_url"] = urljoin(self.public_base_url, data["audio_url"].lstrip("/"))
        return SpeechResult.model_validate(data)

    async def health(self) -> dict:
        return await self._call("GET", "/health")

    async def _call(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = await self._client.request(method, f"{self.base_url}{path}", **kwargs)
        except httpx.HTTPError as exc:
            raise SpeechServiceError(
                f"speech service unreachable at {self.base_url}: {exc}"
            ) from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = response.text[:200]
            raise SpeechServiceError(f"speech service returned {response.status_code}: {detail}")
        return response.json()

    async def aclose(self) -> None:
        await self._client.aclose()


def get_speech_client() -> SpeechClient:
    """FastAPI dependency; the address comes from SPEECH_SERVICE_URL (backend/.env).

    Audio URLs point at the backend's proxy (/api/speech/audio/...), so the browser
    reaches them through the same address as the rest of the API.
    """
    return HttpSpeechClient(
        base_url=get_settings().speech_service_url, public_base_url=PUBLIC_AUDIO_BASE
    )
