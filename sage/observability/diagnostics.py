"""Runtime diagnostics and observability helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from sage.contracts import DiagnosticStatus, RuntimeSettings


def run_diagnostics(settings: RuntimeSettings) -> list[DiagnosticStatus]:
    return [
        _binary_status("ffmpeg"),
        _binary_status("rg"),
        _binary_status("ollama"),
        _binary_status(settings.piper_binary_path, required=False),
        _binary_status(settings.audio_player, required=False),
        DiagnosticStatus(
            name="database",
            ok=settings.database_path.parent.exists() or _can_create_parent(settings.database_path),
            detail=str(settings.database_path),
        ),
        DiagnosticStatus(
            name="piper_voice",
            ok=settings.piper_voice_path is not None and settings.piper_voice_path.exists(),
            detail=(
                str(settings.piper_voice_path)
                if settings.piper_voice_path
                else "not configured"
            ),
        ),
    ]


def _binary_status(name: str, required: bool = True) -> DiagnosticStatus:
    path = shutil.which(name)
    return DiagnosticStatus(
        name=name,
        ok=path is not None or not required,
        detail=path or ("missing" if required else "optional missing"),
    )


def _can_create_parent(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return True
