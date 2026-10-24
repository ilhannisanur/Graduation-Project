from abc import ABC, abstractmethod


class SpeechClient(ABC):
    """Interface to the separate speech (TTS) service. Not implemented yet."""

    @abstractmethod
    def synthesize(self, text: str, emotion: str) -> bytes:
        """Return audio bytes for the given text spoken with the given emotion."""
