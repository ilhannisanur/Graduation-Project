from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> project root is three levels above this folder
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://radio:radio@localhost:5433/radio"
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    jamendo_client_id: str = ""
    # Resolved from this file's location, not the working directory.
    music_dir: Path = PROJECT_ROOT / "data" / "music"


@lru_cache
def get_settings() -> Settings:
    return Settings()
