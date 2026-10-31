"""Interface to the speech service (#8)."""

from .client import (
    DEFAULT_SPEECH_URL,
    Emotion,
    HttpSpeechClient,
    SpeechClient,
    SpeechRequest,
    SpeechResult,
    SpeechServiceError,
    get_speech_client,
)

__all__ = [
    "DEFAULT_SPEECH_URL",
    "Emotion",
    "HttpSpeechClient",
    "SpeechClient",
    "SpeechRequest",
    "SpeechResult",
    "SpeechServiceError",
    "get_speech_client",
]
