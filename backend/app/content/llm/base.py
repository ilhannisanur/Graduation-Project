from abc import ABC, abstractmethod
from typing import Any


class LLMError(Exception):
    """Raised when the LLM provider is misconfigured or a call fails."""


class LLMClient(ABC):
    """Provider-independent LLM interface. All LLM access goes through this."""

    @abstractmethod
    def generate_text(self, prompt: str, system: str | None = None) -> str:
        """Return a plain-text completion."""

    @abstractmethod
    def generate_json(self, prompt: str, system: str | None = None) -> dict[str, Any]:
        """Return a completion parsed as a JSON object."""
