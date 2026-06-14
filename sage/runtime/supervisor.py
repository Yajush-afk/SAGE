"""Local development stack supervisor."""

from __future__ import annotations

import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request
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
    readiness_timeout_seconds: float = 20,
) -> int:
    """Start Whisper.cpp, the SAGE daemon, and optionally the Electron control panel."""
    root = repo_root or Path.cwd()
    preflight_stack_ports(
        settings,
        host=host,
        port=port,
        with_ui=with_ui,
        ui_host=ui_host,
        ui_port=ui_port,
    )
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
        if settings.whisper_provider == "whisper_cpp_http":
            print(f"External Whisper endpoint: {settings.whisper_endpoint}", flush=True)
        if with_ui:
            print(f"Control panel: http://{ui_host}:{ui_port}", flush=True)
        wait_for_stack_readiness(
            settings,
            host=host,
            port=port,
            with_ui=with_ui,
            ui_host=ui_host,
            ui_port=ui_port,
            timeout_seconds=readiness_timeout_seconds,
        )
        print("Press Ctrl+C to stop SAGE.", flush=True)

        while True:
            for name, process in processes:
                return_code = process.poll()
                if return_code is not None:
                    _print_process_exit(name, process, return_code)
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
    processes = []
    if settings.whisper_provider == "whisper_cpp":
        processes.append(StackProcess("whisper.cpp", _whisper_server_command(settings)))
    elif settings.whisper_provider != "whisper_cpp_http":
        raise RuntimeError(
            f"sage start only supports whisper_cpp or external whisper_cpp_http, "
            f"not {settings.whisper_provider}"
        )

    processes.append(
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
    )
    if with_ui:
        processes.append(_ui_process(ui_host=ui_host, ui_port=ui_port, repo_root=repo_root))
    return processes


def _whisper_server_command(settings: RuntimeSettings) -> list[str]:
    if settings.whisper_provider != "whisper_cpp":
        raise RuntimeError(
            f"sage start only manages whisper_cpp, not {settings.whisper_provider}"
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


def preflight_stack_ports(
    settings: RuntimeSettings,
    *,
    host: str,
    port: int,
    with_ui: bool,
    ui_host: str,
    ui_port: int,
) -> None:
    checks = [("SAGE daemon", host, port)]
    if settings.whisper_provider == "whisper_cpp":
        whisper_host, whisper_port, _ = _parse_whisper_endpoint(settings.whisper_endpoint)
        checks.append(("Whisper.cpp", whisper_host, whisper_port))
    if with_ui:
        checks.append(("control panel", ui_host, ui_port))

    for name, check_host, check_port in checks:
        if _port_is_open(check_host, check_port):
            raise RuntimeError(
                f"{name} port is already in use: {check_host}:{check_port}. "
                "Stop the existing process or choose another port."
            )


def wait_for_stack_readiness(
    settings: RuntimeSettings,
    *,
    host: str,
    port: int,
    with_ui: bool,
    ui_host: str,
    ui_port: int,
    timeout_seconds: float,
) -> None:
    if timeout_seconds <= 0:
        return

    checks = [("SAGE daemon", f"http://{host}:{port}/health")]
    if settings.whisper_provider in {"whisper_cpp", "whisper_cpp_http"}:
        checks.append(("Whisper.cpp", settings.whisper_endpoint))
    if with_ui:
        checks.append(("control panel", f"http://{ui_host}:{ui_port}"))

    for name, url in checks:
        _wait_for_http(name, url, timeout_seconds)


def _wait_for_http(name: str, url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            request.urlopen(url, timeout=0.5).close()
            print(f"{name} ready: {url}", flush=True)
            return
        except error.HTTPError:
            print(f"{name} ready: {url}", flush=True)
            return
        except (OSError, TimeoutError, error.URLError) as exc:
            last_error = str(exc)
            time.sleep(0.25)
    raise RuntimeError(f"{name} did not become ready at {url}: {last_error}")


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def _print_process_exit(name: str, process: subprocess.Popen[bytes], return_code: int) -> None:
    args = getattr(process, "args", None) or getattr(process, "command", None)
    command = " ".join(str(part) for part in args) if args else "unknown command"
    print(f"{name} exited with code {return_code}", flush=True)
    print(f"{name} command: {command}", flush=True)


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
