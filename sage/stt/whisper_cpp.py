"""Whisper.cpp speech-to-text adapters."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Protocol
from urllib import error, request
from uuid import uuid4

from sage.contracts import RuntimeSettings, TranscriptionResult


class TranscriptionError(RuntimeError):
    """Raised when local speech-to-text fails."""


class STTProvider(Protocol):
    def transcribe(self, audio_path: Path, settings: RuntimeSettings) -> TranscriptionResult: ...


class WhisperCppHttpProvider:
    """Call a Whisper.cpp/OpenAI-compatible local transcription endpoint."""

    def transcribe(self, audio_path: Path, settings: RuntimeSettings) -> TranscriptionResult:
        if not audio_path.exists():
            raise TranscriptionError(f"audio file does not exist: {audio_path}")

        endpoint = self._transcription_endpoint(settings.whisper_endpoint)
        body, content_type = self._multipart_body(audio_path)
        req = request.Request(
            url=endpoint,
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": content_type,
            },
            method="POST",
        )

        started_at = time.monotonic()
        try:
            with request.urlopen(req, timeout=120) as response:
                raw_body = response.read().decode("utf-8")
        except error.URLError as exc:
            raise TranscriptionError(f"could not reach Whisper.cpp endpoint: {exc}") from exc

        duration_ms = int((time.monotonic() - started_at) * 1000)
        text = self._extract_text(raw_body)
        return TranscriptionResult(
            text=text,
            confidence=None,
            duration_ms=duration_ms,
            provider="whisper_cpp_http",
        )

    @staticmethod
    def _transcription_endpoint(base_endpoint: str) -> str:
        normalized = base_endpoint.rstrip("/")
        if normalized.endswith("/audio/transcriptions"):
            return normalized
        return f"{normalized}/audio/transcriptions"

    @staticmethod
    def _multipart_body(audio_path: Path) -> tuple[bytes, str]:
        boundary = f"sage-{uuid4().hex}"
        audio_bytes = audio_path.read_bytes()
        parts = [
            f"--{boundary}\r\n".encode(),
            (
                'Content-Disposition: form-data; name="file"; '
                f'filename="{audio_path.name}"\r\n'
            ).encode(),
            b"Content-Type: audio/wav\r\n\r\n",
            audio_bytes,
            b"\r\n",
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="model"\r\n\r\n',
            b"whisper-1\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
        return b"".join(parts), f"multipart/form-data; boundary={boundary}"

    @staticmethod
    def _extract_text(raw_body: str) -> str:
        stripped = raw_body.strip()
        if not stripped:
            raise TranscriptionError("Whisper.cpp returned an empty transcription response")

        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return stripped

        text = parsed.get("text")
        if not isinstance(text, str) or not text.strip():
            raise TranscriptionError("Whisper.cpp response did not include non-empty text")
        return text.strip()


class WhisperCppCliProvider:
    """Call a local whisper.cpp CLI binary."""

    def transcribe(self, audio_path: Path, settings: RuntimeSettings) -> TranscriptionResult:
        if settings.whisper_model_path is None:
            raise TranscriptionError("whisper_model_path must be configured for whisper_cpp_cli")
        if not audio_path.exists():
            raise TranscriptionError(f"audio file does not exist: {audio_path}")

        command = [
            settings.whisper_cli_path,
            "-m",
            str(settings.whisper_model_path),
            "-f",
            str(audio_path),
            "-nt",
        ]

        started_at = time.monotonic()
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        duration_ms = int((time.monotonic() - started_at) * 1000)

        if completed.returncode != 0:
            raise TranscriptionError(completed.stderr.strip() or "whisper.cpp CLI failed")

        text = self._extract_cli_text(completed.stdout)
        return TranscriptionResult(
            text=text,
            confidence=None,
            duration_ms=duration_ms,
            provider="whisper_cpp_cli",
        )

    @staticmethod
    def _extract_cli_text(stdout: str) -> str:
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        if not lines:
            raise TranscriptionError("whisper.cpp CLI returned empty output")
        return " ".join(lines)


def build_stt_provider(settings: RuntimeSettings) -> STTProvider:
    if settings.whisper_provider in {"whisper_cpp", "whisper_cpp_http"}:
        return WhisperCppHttpProvider()
    if settings.whisper_provider == "whisper_cpp_cli":
        return WhisperCppCliProvider()
    raise TranscriptionError(f"unsupported whisper provider: {settings.whisper_provider}")
