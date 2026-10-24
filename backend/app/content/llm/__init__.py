from app.content.llm.base import LLMClient, LLMError
from app.content.llm.gemini import GeminiClient
from app.core.config import get_settings


def get_llm_client() -> LLMClient:
    """Build the LLM client chosen by LLM_PROVIDER. Add new providers here."""
    settings = get_settings()
    if settings.llm_provider == "gemini":
        return GeminiClient(settings.gemini_api_key, settings.gemini_model)
    raise LLMError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")


__all__ = ["GeminiClient", "LLMClient", "LLMError", "get_llm_client"]
