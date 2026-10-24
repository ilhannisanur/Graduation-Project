from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict


class RequestStatus(StrEnum):
    RECEIVED = "received"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PLAYED = "played"


class RequestIntent(BaseModel):
    """What the listener asked for, as understood by DJ Brain."""

    model_config = ConfigDict(extra="forbid")

    song_title: str | None = None
    artist: str | None = None
    mood: str | None = None
    message: str | None = None


class SongRequest(BaseModel):
    """A listener's written song request. Tracked by Music & Platform."""

    model_config = ConfigDict(extra="forbid")

    id: str
    session_id: str
    raw_text: str
    intent: RequestIntent | None = None
    status: RequestStatus
    reject_reason: str | None = None
    estimated_play_time: AwareDatetime | None = None
