"""M1 integration (#12): connects the broadcast planner (#9) to the real modules.

    music    CatalogMusicSource (#11)     songs from the catalog in Postgres
    director SongIntroDirector (#6)       the intro, written by the LLM (Gemini)
    speech   SpeechClientSynthesizer (#8) the voice, from the separate speech service

The FastAPI app runs ``radio_lifespan`` (app/main.py): the planner is built when the
backend starts and its background work is cancelled when it stops.

What happens when a part is missing (the radio never goes silent):

* No GEMINI_API_KEY: the director cannot reach the LLM and uses DJ Brain's template
  intro ("Up next, <title> by <artist>."), which is still voiced.
* Speech service not running: announcements are skipped, songs keep playing. Once
  the service is started, announcements come back by themselves (no restart).
* Empty catalog or database down: /api/sessions/{id}/next answers 503
  "No song available right now" (README, "Müzik kataloğu").
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from app.content.director import SongIntroDirector
from app.content.llm import LLMClient, LLMError, get_llm_client
from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.music.source import CatalogMusicSource, SessionFactory
from app.radio.planner import (
    BroadcastPlanner,
    MusicSource,
    PlannerSettings,
    configure_planner,
    current_planner,
    shutdown_planner,
)
from app.radio.planner.adapters import SpeechClientSynthesizer
from app.speech_client import (
    PUBLIC_AUDIO_BASE,
    HttpSpeechClient,
    SpeechClient,
    SpeechServiceError,
)

logger = logging.getLogger(__name__)

STARTUP_CHECK_TIMEOUT_S = 3.0


class UnavailableLLM(LLMClient):
    """Stands in when no LLM is configured, so the reason shows up in one place.

    Every call raises ``LLMError``; ``generate_song_intro`` then returns its template
    intro. Nothing is invented here: the text is DJ Brain's own fallback.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def generate_text(self, prompt: str, system: str | None = None) -> str:
        raise LLMError(self.reason)

    def generate_json(self, prompt: str, system: str | None = None) -> dict[str, Any]:
        raise LLMError(self.reason)


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "gemini" and not settings.gemini_api_key.strip():
        reason = "GEMINI_API_KEY is empty in backend/.env"
    else:
        try:
            return get_llm_client()
        except LLMError as exc:
            reason = str(exc)
    logger.warning("LLM not available (%s): announcements use the template intro", reason)
    return UnavailableLLM(reason)


def build_planner(
    settings: Settings | None = None,
    *,
    session_factory: SessionFactory | None = None,
    music: MusicSource | None = None,
    llm: LLMClient | None = None,
    speech_client: SpeechClient | None = None,
    planner_settings: PlannerSettings | None = None,
) -> BroadcastPlanner:
    """The planner with the real modules. Tests pass fakes for the outside edges only."""
    settings = settings or get_settings()
    session_factory = session_factory or sessionmaker(bind=get_engine())
    speech_client = speech_client or HttpSpeechClient(
        base_url=settings.speech_service_url, public_base_url=PUBLIC_AUDIO_BASE
    )
    return BroadcastPlanner(
        music=music or CatalogMusicSource(session_factory),
        director=SongIntroDirector(llm or build_llm(settings), session_factory),
        speech=SpeechClientSynthesizer(speech_client),
        settings=planner_settings,
    )


async def check_speech_service(speech: SpeechClient) -> None:
    """Log at startup whether announcements can be voiced. Never stops the backend."""
    try:
        health = await asyncio.wait_for(speech.health(), timeout=STARTUP_CHECK_TIMEOUT_S)
    except (SpeechServiceError, TimeoutError) as exc:
        logger.warning(
            "speech service not reachable (%s): songs play without announcements "
            "until it is started (speech/service/README.md)",
            str(exc) or f"no answer in {STARTUP_CHECK_TIMEOUT_S:g} s",
        )
        return
    primary = health.get("primary") or {}
    logger.info(
        "speech service %s, engine %s on %s",
        health.get("status"),
        primary.get("engine"),
        primary.get("device"),
    )


@asynccontextmanager
async def radio_lifespan(app: FastAPI) -> AsyncIterator[None]:
    if current_planner() is not None:  # already wired, e.g. by a test with fakes
        yield
        return

    planner = build_planner()
    speech = planner.speech
    configure_planner(planner)
    if isinstance(speech, SpeechClientSynthesizer):
        await check_speech_service(speech.client)
    try:
        yield
    finally:
        await shutdown_planner()
        configure_planner(None)
        if isinstance(speech, SpeechClientSynthesizer):
            await speech.aclose()
