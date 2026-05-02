"""Piper-backed local text-to-speech provider."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sage.contracts import RuntimeSettings, SpeechResult


class TTSError(RuntimeError):
    """Raised when local speech synthesis fails."""


class TTSProvider(Protocol):
    def speak(self, text: str, settings: RuntimeSettings) -> SpeechResult: ...


class PiperTTSProvider:
    """Synthesize concise spoken responses with Piper."""

    def speak(self, text: str, settings: RuntimeSettings) -> SpeechResult:
        if not settings.piper_enabled:
            return SpeechResult(success=True, provider="disabled", text=text)
        if settings.piper_voice_path is None:
            return SpeechResult(
                success=False,
                provider="piper",
                text=text,
                error="piper_voice_path is not configured",
            )

        output_path = Path(tempfile.gettempdir()) / f"sage_tts_{uuid4().hex}.wav"
        synth = subprocess.run(
            [
                settings.piper_binary_path,
                "--model",
                str(settings.piper_voice_path),
                "--output_file",
                str(output_path),
            ],
            input=text,
            capture_output=True,
            text=True,
            check=False,
        )
        if synth.returncode != 0:
            return SpeechResult(
                success=False,
                provider="piper",
                text=text,
                audio_path=output_path,
                error=synth.stderr.strip() or "piper synthesis failed",
            )

        play = subprocess.run(
            [
                settings.audio_player,
                "-nodisp",
                "-autoexit",
                "-loglevel",
                "quiet",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if play.returncode != 0:
            return SpeechResult(
                success=False,
                provider="piper",
                text=text,
                audio_path=output_path,
                error=play.stderr.strip() or "audio playback failed",
            )

        return SpeechResult(success=True, provider="piper", text=text, audio_path=output_path)


class NullTTSProvider:
    """No-op TTS provider for tests and muted setups."""

    def speak(self, text: str, settings: RuntimeSettings) -> SpeechResult:
        return SpeechResult(success=True, provider="null", text=text)
