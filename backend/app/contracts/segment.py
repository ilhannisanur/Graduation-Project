from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.contracts.announcement import AnnouncementSpec


class _SegmentBase(BaseModel):
    """Fields shared by every queue item. The scheduler tracks items by id and plans by duration."""

    model_config = ConfigDict(extra="forbid")

    id: str
    duration_seconds: float | None = Field(default=None, gt=0)


class TrackSegment(_SegmentBase):
    """A song to play. Produced by Music & Platform."""

    type: Literal["track"] = "track"
    track_id: str
    selection_reason: str | None = None  # answers "why this song?"
    request_id: str | None = None  # set when the song plays because of a listener request


class AnnouncementSegment(_SegmentBase):
    """A DJ announcement. The spec comes from DJ Brain; Voice & Broadcast fills audio_url."""

    type: Literal["announcement"] = "announcement"
    spec: AnnouncementSpec
    audio_url: str | None = None


class BulletinItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    source_name: str
    source_url: str
    published_at: AwareDatetime


class BulletinSegment(_SegmentBase):
    """A news bulletin. Produced by DJ Brain."""

    type: Literal["bulletin"] = "bulletin"
    items: list[BulletinItem] = Field(min_length=1)


Segment = Annotated[
    TrackSegment | AnnouncementSegment | BulletinSegment,
    Field(discriminator="type"),
]
