from pydantic import BaseModel, ConfigDict, Field


class Track(BaseModel):
    """A music track as shared between modules.

    Produced by Music & Platform. The audio file path is intentionally absent:
    it is an internal detail of the database.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    artist: str
    duration_seconds: float = Field(gt=0)
    license: str  # e.g. "CC BY 4.0"
    license_url: str
    source_url: str
    mood_tags: list[str] = Field(default_factory=list)
    # Filled by music analysis (S4); both range from 0 to 1.
    valence: float | None = Field(default=None, ge=0, le=1)
    arousal: float | None = Field(default=None, ge=0, le=1)
