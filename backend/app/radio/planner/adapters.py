"""Adapter for the Speech service (#8), which runs as a separate process.

The request/response shape below is the proposal for the Speech service API:

    POST {base_url}/synthesize
    {"text": "...", "emotion": "calm", "intensity": 0.6, "voice_id": null,
     "target_duration_s": 12.0}
    -> 200 {"audio_url": "/audio/3f2a.wav", "duration_s": 11.4}

A relative ``audio_url`` is turned into an absolute one with
``public_base_url``, so the browser can fetch the file.

Adapters for the music source (#11) and the director (#6) are written in the
integration (#12), once their functions are merged.
"""

from __future__ import annotations

from urllib.parse import urljoin

import httpx

from .models import AnnouncementPlan, SpeechAudio


class HttpSpeechSynthesizer:
    def __init__(
        self,
        base_url: str,
        public_base_url: str | None = None,
        timeout_s: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.public_base_url = (public_base_url or base_url).rstrip("/") + "/"
        self._client = client or httpx.AsyncClient(timeout=timeout_s)

    async def synthesize(self, plan: AnnouncementPlan) -> SpeechAudio:
        response = await self._client.post(
            f"{self.base_url}/synthesize",
            json=plan.model_dump(
                include={
                    "text",
                    "emotion",
                    "intensity",
                    "voice_id",
                    "target_duration_s",
                }
            ),
        )
        response.raise_for_status()
        audio = SpeechAudio.model_validate(response.json())
        audio.audio_url = urljoin(self.public_base_url, audio.audio_url)
        return audio

    async def aclose(self) -> None:
        await self._client.aclose()
