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
    # Comma-separated models tried in order when the main one fails (e.g. "high demand").
    gemini_fallback_models: str = ""
    jamendo_client_id: str = ""
    # Resolved from this file's location, not the working directory.
    music_dir: Path = PROJECT_ROOT / "data" / "music"
    # Send the login cookie only over HTTPS. Must be true in production; local dev uses http.
    cookie_secure: bool = False
    # The speech (TTS) service, a separate process (speech/service). The browser never
    # calls it directly: announcement audio is served through /api/speech/audio/.
    speech_service_url: str = "http://localhost:8001"
    # How long the player may wait for an unfinished announcement (0 = never wait, play the
    # song). A demo where songs are skipped quickly sets e.g. 30, so the DJ is still heard.
    planner_announcement_wait_s: float = 0.0
    # Longest time spent writing and voicing one announcement in the background. Orpheus on
    # an 8 GB laptop GPU can need 1-2 minutes per line; a demo on that laptop sets e.g. 240.
    planner_announcement_timeout_s: float = 90.0
    # Address phones use to reach the request page, for the QR code on the studio screen,
    # e.g. http://192.168.137.1:5173. Empty: guessed from the computer's network address.
    public_web_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
