"""Text-to-speech provider package."""

from sage.tts.piper import NullTTSProvider, PiperTTSProvider, TTSError, TTSProvider

__all__ = ["NullTTSProvider", "PiperTTSProvider", "TTSError", "TTSProvider"]
