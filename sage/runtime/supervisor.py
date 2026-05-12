"""Local development stack supervisor."""

from __future__ import annotations

import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from sage.contracts import RuntimeSettings


@dataclass(frozen=True)
class StackProcess:
    name: str
    command: list[str]
    cwd: Path | None = None


def start_stack(
    settings: RuntimeSettings,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    with_ui: bool = False,
    ui_host: str = "127.0.0.1",
    ui_port: int = 5174,
    repo_root: Path | None = None,
) -> int:
    """Start Whisper.cpp, the SAGE daemon, and optionally the Electron control panel."""
    root = repo_root or Path.cwd()
    specs = build_stack_processes(
        settings,
        host=host,
        port=port,
        with_ui=with_ui,
        ui_host=ui_host,
        ui_port=ui_port,
        repo_root=root,
    )
    processes: list[tuple[str, subprocess.Popen[bytes]]] = []
    stop_requested = False

    def request_stop(signum: int, frame: object) -> None:
        nonlocal stop_requested
        stop_requested = True

    previous_sigterm = signal.signal(signal.SIGTERM, request_stop)
    previous_sigint = signal.signal(signal.SIGINT, request_stop)
    try:
        for spec in specs:
            print(f"starting {spec.name}: {' '.join(spec.command)}", flush=True)
            processes.append((spec.name, subprocess.Popen(spec.command, cwd=spec.cwd)))

        print(f"SAGE daemon: http://{host}:{port}", flush=True)
        if with_ui:
            print(f"Control panel: http://{ui_host}:{ui_port}", flush=True)
        print("Press Ctrl+C to stop SAGE.", flush=True)

        while True:
            for name, process in processes:
                return_code = process.poll()
                if return_code is not None:
                    print(f"{name} exited with code {return_code}", flush=True)
                    return return_code
            if stop_requested:
                return 130
            time.sleep(0.5)
    finally:
        _terminate_processes(processes)
        signal.signal(signal.SIGTERM, previous_sigterm)
        signal.signal(signal.SIGINT, previous_sigint)


def build_stack_processes(
    settings: RuntimeSettings,
    *,
    host: str,
    port: int,
    with_ui: bool,
    ui_host: str,
    ui_port: int,
    repo_root: Path,
) -> list[StackProcess]:
    processes = [
        StackProcess("whisper.cpp", _whisper_server_command(settings)),
        StackProcess(
            "sage-daemon",
            [
                sys.executable,
                "-m",
                "sage.cli",
                "daemon",
                "start",
                "--host",
                host,
                "--port",
                str(port),
            ],
            cwd=repo_root,
        ),
    ]
    if with_ui:
        processes.append(_ui_process(ui_host=ui_host, ui_port=ui_port, repo_root=repo_root))
    return processes


def _whisper_server_command(settings: RuntimeSettings) -> list[str]:
    if settings.whisper_provider not in {"whisper_cpp", "whisper_cpp_http"}:
        raise RuntimeError(
            f"sage start only manages Whisper.cpp HTTP mode, not {settings.whisper_provider}"
        )
    if settings.whisper_model_path is None:
        raise RuntimeError("whisper_model_path must be configured before running sage start")
    if not settings.whisper_model_path.exists():
        raise RuntimeError(f"Whisper model is missing: {settings.whisper_model_path}")

    whisper_server = _resolve_whisper_server(settings.whisper_cli_path)
    host, port, inference_path = _parse_whisper_endpoint(settings.whisper_endpoint)
    return [
        str(whisper_server),
        "--model",
        str(settings.whisper_model_path),
        "--host",
        host,
        "--port",
        str(port),
        "--inference-path",
        inference_path,
        "--threads",
        "4",
        "--processors",
        "1",
        "--convert",
    ]


def _resolve_whisper_server(whisper_cli_path: str) -> Path:
    cli_path = Path(whisper_cli_path)
    if cli_path.parent != Path("."):
        sibling = cli_path.parent / "whisper-server"
        if sibling.exists():
            return sibling
    found = shutil.which("whisper-server")
    if found:
        return Path(found)
    raise RuntimeError("whisper-server was not found")


def _parse_whisper_endpoint(endpoint: str) -> tuple[str, int, str]:
    parsed = urlparse(endpoint)
    if not parsed.hostname or not parsed.port:
        raise RuntimeError(f"whisper_endpoint must include host and port: {endpoint}")
    base_path = parsed.path.rstrip("/")
    inference_path = f"{base_path}/audio/transcriptions" if base_path else "/audio/transcriptions"
    return parsed.hostname, parsed.port, inference_path


def _ui_process(*, ui_host: str, ui_port: int, repo_root: Path) -> StackProcess:
    ui_dir = repo_root / "apps" / "electron-control-panel"
    package_json = ui_dir / "package.json"
    if not package_json.exists():
        raise RuntimeError(f"Electron control panel was not found: {ui_dir}")
    return StackProcess(
        "control-panel",
        ["npm", "run", "dev", "--", "--host", ui_host, "--port", str(ui_port)],
        cwd=ui_dir,
    )


def _terminate_processes(processes: list[tuple[str, subprocess.Popen[bytes]]]) -> None:
    for _, process in reversed(processes):
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 5
    for _, process in reversed(processes):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            pass
    for _, process in reversed(processes):
        if process.poll() is None:
            process.kill()
