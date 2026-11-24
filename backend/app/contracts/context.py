from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class ListenerContext(BaseModel):
    """Non-identifying context about a listener. The broadcast is shared: this is one of the
    tastes that count together in the selection score's profile part.

    WARNING: this model may be sent to an LLM. It must NEVER contain personal data
    such as name, e-mail or phone number. extra="forbid" rejects unknown fields so
    such data cannot slip in by accident.
    """

    model_config = ConfigDict(extra="forbid")

    local_time: AwareDatetime
    weather_summary: str | None = None
    preferred_genres: list[str] = Field(default_factory=list)
