"""Audio recording providers for push-to-talk commands."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sage.contracts import AudioRecording, RuntimeSettings


class AudioRecordingError(RuntimeError):
    """Raised when local audio capture fails."""


class AudioRecorder(Protocol):
    def record_once(self, settings: RuntimeSettings) -> AudioRecording: ...


class FfmpegAudioRecorder:
    """Record one bounded WAV file through ffmpeg/PulseAudio/PipeWire."""

    def record_once(self, settings: RuntimeSettings) -> AudioRecording:
        output_dir = settings.audio_cache_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"command_{uuid4().hex}.wav"

        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "pulse",
            "-i",
            settings.audio_input,
            "-ac",
            str(settings.audio_channels),
            "-ar",
            str(settings.audio_sample_rate_hz),
            "-t",
            str(settings.max_recording_seconds),
            str(output_path),
        ]

        started_at = time.monotonic()
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        duration_ms = int((time.monotonic() - started_at) * 1000)

        if completed.returncode != 0:
            raise AudioRecordingError(completed.stderr.strip() or "ffmpeg audio recording failed")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise AudioRecordingError("ffmpeg did not produce an audio file")

        return AudioRecording(
            path=Path(output_path),
            duration_ms=duration_ms,
            sample_rate_hz=settings.audio_sample_rate_hz,
            channels=settings.audio_channels,
        )
