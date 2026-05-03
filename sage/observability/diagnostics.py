"""Runtime diagnostics and observability helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from urllib import error, request

from sage.contracts import DiagnosticStatus, RuntimeSettings


def run_diagnostics(settings: RuntimeSettings) -> list[DiagnosticStatus]:
    return [
        _binary_status("ffmpeg"),
        _binary_status("rg"),
        _binary_status("ollama"),
        _ollama_model_status(settings.model_name),
        _whisper_endpoint_status(
            settings.whisper_endpoint,
            required=settings.whisper_provider in {"whisper_cpp", "whisper_cpp_http"},
        ),
        _binary_status(
            settings.whisper_cli_path,
            required=settings.whisper_provider == "whisper_cpp_cli",
        ),
        _path_status(
            "whisper_model",
            settings.whisper_model_path,
            required=(
                settings.whisper_provider == "whisper_cpp_cli"
                or settings.whisper_model_path is not None
            ),
        ),
        _binary_status(settings.piper_binary_path, required=settings.piper_enabled),
        _binary_status(settings.audio_player, required=settings.piper_enabled),
        DiagnosticStatus(
            name="database",
            ok=settings.database_path.parent.exists() or _can_create_parent(settings.database_path),
            detail=str(settings.database_path),
            required=True,
        ),
        DiagnosticStatus(
            name="piper_voice",
            ok=(
                not settings.piper_enabled
                or (settings.piper_voice_path is not None and settings.piper_voice_path.exists())
            ),
            detail=(
                str(settings.piper_voice_path)
                if settings.piper_voice_path
                else "not configured"
            ),
            required=settings.piper_enabled,
        ),
    ]


def _binary_status(name: str, required: bool = True) -> DiagnosticStatus:
    path = shutil.which(name)
    display_name = Path(name).name
    return DiagnosticStatus(
        name=display_name,
        ok=path is not None or not required,
        detail=path or ("missing" if required else "optional missing"),
        required=required,
    )


def _path_status(name: str, path: Path | None, required: bool = True) -> DiagnosticStatus:
    ok = not required or (path is not None and path.exists())
    return DiagnosticStatus(
        name=name,
        ok=ok,
        detail=str(path) if path else "not configured",
        required=required,
    )


def _ollama_model_status(model_name: str) -> DiagnosticStatus:
    if shutil.which("ollama") is None:
        return DiagnosticStatus(
            name="ollama_model",
            ok=False,
            detail=f"ollama missing; expected {model_name}",
            required=True,
        )
    try:
        completed = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DiagnosticStatus(
            name="ollama_model",
            ok=False,
            detail=f"could not list Ollama models: {exc}",
            required=True,
        )

    installed = _model_is_listed(model_name, completed.stdout)
    return DiagnosticStatus(
        name="ollama_model",
        ok=installed,
        detail=model_name if installed else f"{model_name} not pulled",
        required=True,
    )


def _model_is_listed(model_name: str, output: str) -> bool:
    aliases = {model_name}
    if ":" not in model_name:
        aliases.add(f"{model_name}:latest")
    return any(line.split(maxsplit=1)[0] in aliases for line in output.splitlines() if line.strip())


def _whisper_endpoint_status(endpoint: str, required: bool) -> DiagnosticStatus:
    if not required:
        return DiagnosticStatus(
            name="whisper_endpoint",
            ok=True,
            detail="not required for current whisper_provider",
            required=False,
        )
    try:
        request.urlopen(endpoint, timeout=0.2).close()
    except error.HTTPError:
        return DiagnosticStatus(
            name="whisper_endpoint",
            ok=True,
            detail=endpoint,
            required=True,
        )
    except (OSError, TimeoutError, error.URLError) as exc:
        return DiagnosticStatus(
            name="whisper_endpoint",
            ok=False,
            detail=f"{endpoint} unreachable: {exc}",
            required=True,
        )
    return DiagnosticStatus(
        name="whisper_endpoint",
        ok=True,
        detail=endpoint,
        required=True,
    )


def _can_create_parent(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return True
