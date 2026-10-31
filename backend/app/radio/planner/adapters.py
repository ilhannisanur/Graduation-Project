"""Adapters between the planner and the Speech service (#8).

``SpeechClientSynthesizer`` is the one the application uses (M1 integration, #12):
it speaks through the backend's ``SpeechClient`` (app.speech_client), the same
client every other backend code uses for the speech service.

``HttpSpeechSynthesizer`` is the first version written with the planner (#9),
before the speech service existed. It is kept for its tests and for running the
planner against any server that answers ``POST /synthesize``.

The music source (#11) and the director (#6) adapters live in their own modules:
``app.music.source.CatalogMusicSource`` and ``app.content.director.SongIntroDirector``.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx

from app.speech_client import EMOTIONS, SpeechClient, SpeechRequest

from .models import AnnouncementPlan, SpeechAudio

logger = logging.getLogger(__name__)


class SpeechClientSynthesizer:
    """Implements the planner's ``SpeechSynthesizer`` on top of ``SpeechClient``.

    Errors (service down, 422, 503) are not caught here: the planner catches every
    announcement failure and plays the song without the announcement.
    """

    def __init__(self, client: SpeechClient) -> None:
        self.client = client

    async def synthesize(self, plan: AnnouncementPlan) -> SpeechAudio:
        result = await self.client.synthesize(
            SpeechRequest(
                text=plan.text,
                emotion=speakable_emotion(plan.emotion),
                intensity=plan.intensity,
                voice_id=plan.voice_id,
                target_duration_s=plan.target_duration_s,
            )
        )
        return SpeechAudio(audio_url=result.audio_url, duration_s=result.duration_s)

    async def aclose(self) -> None:
        close = getattr(self.client, "aclose", None)
        if close is not None:
            await close()


def speakable_emotion(emotion: str) -> str:
    """The plan's emotion if the speech service knows it, else neutral.

    An unknown label would make the service answer 422 and the announcement would be
    lost; saying it in a neutral voice is better than not saying it.
    """
    label = emotion.strip().lower()
    if label in EMOTIONS:
        return label
    logger.warning("unknown emotion %r, speaking the announcement as neutral", emotion)
    return "neutral"


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
