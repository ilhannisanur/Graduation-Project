import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.users.options import GENRES, LANGUAGES

USERNAME_PATTERN = re.compile(r"^[a-z0-9_.-]{3,32}$")
PASSWORD_MIN = 8
PASSWORD_MAX = 128  # long enough for passphrases, short enough to keep hashing cheap


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
    # Optional consent; never pre-ticked (explicit consent cannot be a default "yes").
    preference_learning: bool = False

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


def _from_options(values: list[str], options: dict[str, str], what: str) -> list[str]:
    unknown = [v for v in values if v not in options]
    if unknown:
        raise ValueError(f"Unknown {what}: {', '.join(unknown)}")
    return list(dict.fromkeys(values))  # drop duplicates, keep order


class Profile(BaseModel):
    """A listener's music taste. The broadcast is shared, so the tastes of the listeners
    count together when songs are picked; news and weather are station settings."""

    model_config = ConfigDict(extra="forbid")

    genres: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    @field_validator("genres")
    @classmethod
    def check_genres(cls, value: list[str]) -> list[str]:
        return _from_options(value, GENRES, "genre")

    @field_validator("languages")
    @classmethod
    def check_languages(cls, value: list[str]) -> list[str]:
        return _from_options(value, LANGUAGES, "language")


class Option(BaseModel):
    value: str
    label: str


class ProfileOptions(BaseModel):
    genres: list[Option]
    languages: list[Option]


class ConsentState(BaseModel):
    description: str
    granted: bool
    notice_version: str | None  # None: never decided
    updated_at: datetime | None


class ConsentsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preference_learning: bool


class NoticeSection(BaseModel):
    title: str
    text: str


class PrivacyNotice(BaseModel):
    version: str
    sections: list[NoticeSection]
    consents: dict[str, str]  # kind -> what the listener agrees to


class DeleteAccountRequest(BaseModel):
    """The password is asked again so a forgotten open tab cannot delete the account."""

    model_config = ConfigDict(extra="forbid")

    password: str = Field(max_length=PASSWORD_MAX)
