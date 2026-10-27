"""What the planner needs from the other modules.

The planner only talks to these three interfaces. Real implementations are
plugged in during integration (#12); tests use fakes.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .models import AnnouncementPlan, AnnouncementRequest, SpeechAudio, TrackInfo


class MusicSource(Protocol):
    """Music & Platform (#11): picks the next song for a listener."""

    async def next_track(self, *, user_id: str, recent_track_ids: Sequence[str]) -> TrackInfo: ...


class AnnouncementDirector(Protocol):
    """DJ Brain (#6): decides the type, tone and length of an announcement."""

    async def plan(self, request: AnnouncementRequest) -> AnnouncementPlan: ...


class SpeechSynthesizer(Protocol):
    """Voice & Broadcast (#8): turns an announcement plan into audio."""

    async def synthesize(self, plan: AnnouncementPlan) -> SpeechAudio: ...
