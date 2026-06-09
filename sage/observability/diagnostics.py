"""Runtime diagnostics and observability helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from urllib import error, request

from sage.contracts import DiagnosticStatus, RuntimeSettings

DOCS_SETUP = "docs/local-setup.md"


def run_diagnostics(settings: RuntimeSettings) -> list[DiagnosticStatus]:
    return [
        _binary_status(
            "ffmpeg",
            fix_hint="Install ffmpeg with your system package manager.",
            docs_anchor=f"{DOCS_SETUP}#target-environment",
        ),
        _binary_status(
            "rg",
            fix_hint="Install ripgrep with your system package manager.",
            docs_anchor=f"{DOCS_SETUP}#target-environment",
        ),
        _binary_status(
            "ollama",
            fix_hint="Install Ollama, start its service, then pull the configured model.",
            docs_anchor=f"{DOCS_SETUP}#ollama",
        ),
        _ollama_model_status(settings.model_name),
        _whisper_endpoint_status(
            settings.whisper_endpoint,
            required=settings.whisper_provider in {"whisper_cpp", "whisper_cpp_http"},
        ),
        _binary_status(
            settings.whisper_cli_path,
            required=settings.whisper_provider == "whisper_cpp_cli",
            fix_hint="Install whisper.cpp or point whisper_cli_path at whisper-cli.",
            docs_anchor=f"{DOCS_SETUP}#whispercpp",
        ),
        _path_status(
            "whisper_model",
            settings.whisper_model_path,
            required=(
                settings.whisper_provider == "whisper_cpp_cli"
                or settings.whisper_model_path is not None
            ),
            fix_hint="Download a Whisper model and configure whisper_model_path.",
            docs_anchor=f"{DOCS_SETUP}#whispercpp",
        ),
        _binary_status(
            settings.piper_binary_path,
            required=settings.piper_enabled,
            fix_hint="Install Piper or disable piper_enabled in SAGE settings.",
            docs_anchor=f"{DOCS_SETUP}#piper",
        ),
        _binary_status(
            settings.audio_player,
            required=settings.piper_enabled,
            fix_hint="Install ffplay/ffmpeg or configure audio_player to an available player.",
            docs_anchor=f"{DOCS_SETUP}#piper",
        ),
        DiagnosticStatus(
            name="database",
            ok=(
                database_ok := (
                    settings.database_path.parent.exists()
                    or _can_create_parent(settings.database_path)
                )
            ),
            detail=str(settings.database_path),
            required=True,
            severity="ok" if database_ok else "error",
            fix_hint="" if database_ok else (
                "Create the database parent directory or configure database_path to a writable "
                "location."
            ),
            docs_anchor=f"{DOCS_SETUP}#manual-local-wiring",
        ),
        _path_status(
            "piper_voice",
            settings.piper_voice_path,
            required=settings.piper_enabled,
            ok_when_optional_missing=True,
            fix_hint="Download a Piper voice model and configure piper_voice_path.",
            docs_anchor=f"{DOCS_SETUP}#piper",
        ),
    ]


def _binary_status(
    name: str,
    required: bool = True,
    *,
    fix_hint: str = "",
    docs_anchor: str = "",
) -> DiagnosticStatus:
    path = shutil.which(name)
    display_name = Path(name).name
    ok = path is not None or not required
    return DiagnosticStatus(
        name=display_name,
        ok=ok,
        detail=path or ("missing" if required else "optional missing"),
        required=required,
        severity=_severity(ok=ok, required=required, present=path is not None),
        fix_hint="" if path is not None else fix_hint,
        docs_anchor=docs_anchor,
    )


def _path_status(
    name: str,
    path: Path | None,
    required: bool = True,
    *,
    ok_when_optional_missing: bool = True,
    fix_hint: str = "",
    docs_anchor: str = "",
) -> DiagnosticStatus:
    present = path is not None and path.exists()
    ok = present or (not required and ok_when_optional_missing)
    return DiagnosticStatus(
        name=name,
        ok=ok,
        detail=str(path) if path else "not configured",
        required=required,
        severity=_severity(ok=ok, required=required, present=present),
        fix_hint="" if ok else fix_hint,
        docs_anchor=docs_anchor,
    )


def _ollama_model_status(model_name: str) -> DiagnosticStatus:
    if shutil.which("ollama") is None:
        return DiagnosticStatus(
            name="ollama_model",
            ok=False,
            detail=f"ollama missing; expected {model_name}",
            required=True,
            severity="error",
            fix_hint="Install Ollama before checking local models.",
            docs_anchor=f"{DOCS_SETUP}#ollama",
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
            severity="error",
            fix_hint="Start Ollama, then run `ollama list` to verify the service responds.",
            docs_anchor=f"{DOCS_SETUP}#ollama",
        )

    installed = _model_is_listed(model_name, completed.stdout)
    return DiagnosticStatus(
        name="ollama_model",
        ok=installed,
        detail=model_name if installed else f"{model_name} not pulled",
        required=True,
        severity="ok" if installed else "error",
        fix_hint="" if installed else f"Run `ollama pull {model_name}`.",
        docs_anchor=f"{DOCS_SETUP}#ollama",
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
            severity="ok",
            docs_anchor=f"{DOCS_SETUP}#whispercpp",
        )
    try:
        request.urlopen(endpoint, timeout=0.2).close()
    except error.HTTPError:
        return DiagnosticStatus(
            name="whisper_endpoint",
            ok=True,
            detail=endpoint,
            required=True,
            severity="ok",
            docs_anchor=f"{DOCS_SETUP}#whispercpp",
        )
    except (OSError, TimeoutError, error.URLError) as exc:
        return DiagnosticStatus(
            name="whisper_endpoint",
            ok=False,
            detail=f"{endpoint} unreachable: {exc}",
            required=True,
            severity="error",
            fix_hint=(
                "Start SAGE with `sage start`, start whisper-server manually, or configure "
                "whisper_endpoint to the running transcription server."
            ),
            docs_anchor=f"{DOCS_SETUP}#whispercpp",
        )
    return DiagnosticStatus(
        name="whisper_endpoint",
        ok=True,
        detail=endpoint,
        required=True,
        severity="ok",
        docs_anchor=f"{DOCS_SETUP}#whispercpp",
    )


def _can_create_parent(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return True


def _severity(*, ok: bool, required: bool, present: bool) -> str:
    if ok and (required or present):
        return "ok"
    if ok:
        return "warning"
    if required:
        return "error"
    return "warning"
