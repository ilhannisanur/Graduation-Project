import json
from typing import Any

from google import genai
from google.genai import types

from app.content.llm.base import LLMClient, LLMError

TIMEOUT_MS = 15000  # per request, in milliseconds
MAX_RETRIES = 2  # retries after the first one
RETRY_STATUS_CODES = [
    500,
    502,
    504,
]  # 429/503 are not retried here: their Retry-After header can make the library wait minutes


class GeminiClient(LLMClient):
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set")
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=TIMEOUT_MS,
                retry_options=types.HttpRetryOptions(
                    attempts=MAX_RETRIES + 1,
                    http_status_codes=RETRY_STATUS_CODES,
                ),
            ),
        )
        self._model = model

    def generate_text(self, prompt: str, system: str | None = None) -> str:
        return self._create(prompt, system)

    def generate_json(self, prompt: str, system: str | None = None) -> dict[str, Any]:
        text = self._create(
            prompt,
            system,
            response_format={"type": "text", "mime_type": "application/json"},
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("LLM did not return valid JSON") from exc

    def _create(self, prompt: str, system: str | None, **extra: Any) -> str:
        params: dict[str, Any] = {"model": self._model, "input": prompt, **extra}
        if system:
            params["system_instruction"] = system
        try:
            interaction = self._client.interactions.create(**params)
        except Exception as exc:
            raise LLMError(f"Gemini request failed: {exc}") from exc
        return interaction.output_text
