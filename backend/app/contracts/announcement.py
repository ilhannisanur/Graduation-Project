from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.emotion import Emotion


class AnnouncementKind(StrEnum):
    SONG_INTRO = "song_intro"
    BACK_ANNOUNCE = "back_announce"
    REQUEST_SHOUTOUT = "request_shoutout"
    GREETING = "greeting"
    BULLETIN_INTRO = "bulletin_intro"


class AnnouncementSpec(BaseModel):
    """What the DJ will say, in which mood and for how long.

    Produced by DJ Brain, consumed by Voice & Broadcast for speech synthesis.
    """

    model_config = ConfigDict(extra="forbid")

    kind: AnnouncementKind
    text: str = Field(min_length=1)
    emotion: Emotion
    target_seconds: float = Field(ge=3, le=120)
    language: Literal["en"] = "en"
