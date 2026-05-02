"""Speech-to-text provider package."""

from sage.stt.whisper_cpp import (
    STTProvider,
    TranscriptionError,
    WhisperCppCliProvider,
    WhisperCppHttpProvider,
    build_stt_provider,
)

__all__ = [
    "STTProvider",
    "TranscriptionError",
    "WhisperCppCliProvider",
    "WhisperCppHttpProvider",
    "build_stt_provider",
]
