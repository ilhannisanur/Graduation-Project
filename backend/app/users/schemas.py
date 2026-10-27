import re
import unicodedata
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.users.options import GENRES, LANGUAGES, NEWS_TOPICS

USERNAME_PATTERN = re.compile(r"^[a-z0-9_.-]{3,32}$")
PASSWORD_MIN = 8
PASSWORD_MAX = 128  # long enough for passphrases, short enough to keep hashing cheap
MAX_ARTISTS = 20


def fold_turkish_i(text: str) -> str:
    """Map the four Turkish I letters (I, İ, ı, i) to a plain 'i'.

    Python's lower/casefold are not Turkish-aware: 'İ' becomes 'i' + a combining dot, so
    'NİSA' typed on a Turkish keyboard would not match 'nisa'.
    """
    for letter in ("İ", "I", "ı"):
        text = text.replace(letter, "i")
    return text


def normalize_username(username: str) -> str:
    return fold_turkish_i(username.strip()).lower()


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)

    @field_validator("username")
    @classmethod
    def check_username(cls, value: str) -> str:
        value = normalize_username(value)
        if not USERNAME_PATTERN.match(value):
            raise ValueError(
                "Use 3-32 characters with only letters, digits, '.', '_' or '-' (no spaces)."
            )
        return value


class LoginRequest(BaseModel):
    """Not validated like registration: any wrong input gets the same 'wrong login' answer."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(max_length=64)
    password: str = Field(max_length=PASSWORD_MAX)


class UserOut(BaseModel):
    id: str
    username: str
    created_at: datetime


Artist = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


def _artist_key(name: str) -> str:
    """Comparison key so 'BARIŞ MANÇO' and 'Barış Manço' count as one artist."""
    return fold_turkish_i(name).casefold()


def _from_options(values: list[str], options: dict[str, str], what: str) -> list[str]:
    unknown = [v for v in values if v not in options]
    if unknown:
        raise ValueError(f"Unknown {what}: {', '.join(unknown)}")
    return list(dict.fromkeys(values))  # drop duplicates, keep order


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    genres: list[str] = Field(default_factory=list)
    artists: list[Artist] = Field(default_factory=list, max_length=MAX_ARTISTS)
    languages: list[str] = Field(default_factory=list)
    news_topics: list[str] = Field(default_factory=list)
    weather_city: str | None = Field(default=None, max_length=100)

    @field_validator("genres")
    @classmethod
    def check_genres(cls, value: list[str]) -> list[str]:
        return _from_options(value, GENRES, "genre")

    @field_validator("languages")
    @classmethod
    def check_languages(cls, value: list[str]) -> list[str]:
        return _from_options(value, LANGUAGES, "language")

    @field_validator("news_topics")
    @classmethod
    def check_news_topics(cls, value: list[str]) -> list[str]:
        return _from_options(value, NEWS_TOPICS, "news topic")

    @field_validator("artists")
    @classmethod
    def dedupe_artists(cls, value: list[str]) -> list[str]:
        seen: dict[str, str] = {}
        for artist in value:
            artist = unicodedata.normalize("NFC", " ".join(artist.split()))
            seen.setdefault(_artist_key(artist), artist)
        return list(seen.values())

    @field_validator("weather_city")
    @classmethod
    def blank_city_is_none(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None


class Option(BaseModel):
    value: str
    label: str


class ProfileOptions(BaseModel):
    genres: list[Option]
    languages: list[Option]
    news_topics: list[Option]
