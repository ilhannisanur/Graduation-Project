"""Data models of the broadcast planner.

Two groups:

* What the planner receives from other modules (``TrackInfo``,
  ``AnnouncementRequest``, ``AnnouncementPlan``, ``SpeechAudio``). The real
  modules return their own contract types (``app/contracts``); the adapters
  wired in #12 convert them into these small models, so the planner does not
  depend on the details of every contract.
* What the planner serves to the player (``QueuedTrack``,
  ``QueuedAnnouncement``, ``NextSegmentResponse``). Unlike the contract's
  TrackSegment, a queued segment always carries a playable ``audio_url``.
  The final shape of the ``/next`` response is agreed with #10 (web player).
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def new_segment_id() -> str:
    return uuid4().hex[:12]


# --- input from other modules -------------------------------------------------


class TrackInfo(BaseModel):
    """A song chosen by Music & Platform (#11)."""

    track_id: str
    title: str
    artist: str
    duration_s: float = Field(gt=0)
    license: str | None = None
    reason: str | None = None  # "why this song?" (filled from S5 on)


class AnnouncementRequest(BaseModel):
    """What the director (#6) needs to write the announcement between two songs.

    Contains no user data on purpose: personal data never goes to the LLM.
    """

    kind: Literal["song_intro"] = "song_intro"
    previous_track: TrackInfo | None
    next_track: TrackInfo


class AnnouncementPlan(BaseModel):
    """The director's decision: what to say, in which emotion, how long."""

    text: str = Field(min_length=1)
    emotion: str = "neutral"
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    target_duration_s: float | None = None
    voice_id: str | None = None


class SpeechAudio(BaseModel):
    """Result of the Speech service (#8)."""

    audio_url: str
    duration_s: float = Field(gt=0)


# --- output to the player -----------------------------------------------------


class QueuedTrack(BaseModel):
    kind: Literal["track"] = "track"
    segment_id: str = Field(default_factory=new_segment_id)
    track_id: str
    title: str
    artist: str
    license: str | None = None
    reason: str | None = None
    duration_s: float
    audio_url: str


class QueuedAnnouncement(BaseModel):
    kind: Literal["announcement"] = "announcement"
    segment_id: str = Field(default_factory=new_segment_id)
    text: str
    emotion: str
    duration_s: float
    audio_url: str
    introduces_track_id: str  # the track that is played right after it


QueuedSegment = Annotated[QueuedTrack | QueuedAnnouncement, Field(discriminator="kind")]


class NextSegmentResponse(BaseModel):
    session_id: str
    position: int  # 1 = first segment of the session
    segment: QueuedSegment
    announcement_skipped: str | None = None  # why a planned announcement was skipped


class SessionCreated(BaseModel):
    session_id: str
    user_id: str
