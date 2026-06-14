import socket
from pathlib import Path
from urllib.error import HTTPError

import pytest

from sage.contracts import RuntimeSettings
from sage.runtime.supervisor import (
    build_stack_processes,
    preflight_stack_ports,
    start_stack,
    wait_for_stack_readiness,
)


def test_build_stack_processes_starts_whisper_and_daemon(tmp_path):
    whisper_dir = tmp_path / "whisper"
    whisper_dir.mkdir()
    whisper_cli = whisper_dir / "whisper-cli"
    whisper_server = whisper_dir / "whisper-server"
    whisper_cli.write_text("", encoding="utf-8")
    whisper_server.write_text("", encoding="utf-8")
    model = tmp_path / "ggml-small.en.bin"
    model.write_text("", encoding="utf-8")

    settings = RuntimeSettings(
        whisper_endpoint="http://127.0.0.1:2022/v1",
        whisper_cli_path=str(whisper_cli),
        whisper_model_path=model,
    )

    processes = build_stack_processes(
        settings,
        host="127.0.0.1",
        port=8765,
        with_ui=False,
        ui_host="127.0.0.1",
        ui_port=5174,
        repo_root=Path("/repo"),
    )

    assert [process.name for process in processes] == ["whisper.cpp", "sage-daemon"]
    assert processes[0].command[:7] == [
        str(whisper_server),
        "--model",
        str(model),
        "--host",
        "127.0.0.1",
        "--port",
        "2022",
    ]
    assert processes[0].command[
        processes[0].command.index("--inference-path") + 1
    ] == "/v1/audio/transcriptions"
    assert processes[1].command[-4:] == ["--host", "127.0.0.1", "--port", "8765"]


def test_build_stack_processes_can_include_ui(tmp_path):
    whisper_dir = tmp_path / "whisper"
    whisper_dir.mkdir()
    whisper_cli = whisper_dir / "whisper-cli"
    whisper_server = whisper_dir / "whisper-server"
    whisper_cli.write_text("", encoding="utf-8")
    whisper_server.write_text("", encoding="utf-8")
    model = tmp_path / "ggml-small.en.bin"
    model.write_text("", encoding="utf-8")
    ui_dir = tmp_path / "apps" / "electron-control-panel"
    ui_dir.mkdir(parents=True)
    (ui_dir / "package.json").write_text("{}", encoding="utf-8")

    processes = build_stack_processes(
        RuntimeSettings(whisper_cli_path=str(whisper_cli), whisper_model_path=model),
        host="127.0.0.1",
        port=8765,
        with_ui=True,
        ui_host="127.0.0.1",
        ui_port=5174,
        repo_root=tmp_path,
    )

    assert [process.name for process in processes] == [
        "whisper.cpp",
        "sage-daemon",
        "control-panel",
    ]
    assert processes[2].command == [
        "npm",
        "run",
        "dev",
        "--",
        "--host",
        "127.0.0.1",
        "--port",
        "5174",
    ]


def test_build_stack_processes_uses_external_whisper_http_mode(tmp_path):
    ui_dir = tmp_path / "apps" / "electron-control-panel"
    ui_dir.mkdir(parents=True)
    (ui_dir / "package.json").write_text("{}", encoding="utf-8")

    processes = build_stack_processes(
        RuntimeSettings(whisper_provider="whisper_cpp_http"),
        host="127.0.0.1",
        port=8765,
        with_ui=True,
        ui_host="127.0.0.1",
        ui_port=5174,
        repo_root=tmp_path,
    )

    assert [process.name for process in processes] == ["sage-daemon", "control-panel"]


def test_build_stack_processes_requires_whisper_model(tmp_path):
    with pytest.raises(RuntimeError, match="whisper_model_path"):
        build_stack_processes(
            RuntimeSettings(whisper_model_path=None),
            host="127.0.0.1",
            port=8765,
            with_ui=False,
            ui_host="127.0.0.1",
            ui_port=5174,
            repo_root=tmp_path,
        )


def test_preflight_stack_ports_reports_busy_daemon_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        busy_port = listener.getsockname()[1]

        with pytest.raises(RuntimeError, match="SAGE daemon port is already in use"):
            preflight_stack_ports(
                RuntimeSettings(whisper_provider="whisper_cpp_http"),
                host="127.0.0.1",
                port=busy_port,
                with_ui=False,
                ui_host="127.0.0.1",
                ui_port=5174,
            )


def test_wait_for_stack_readiness_accepts_http_errors_as_ready(monkeypatch):
    calls = []

    def fake_urlopen(url, timeout):
        calls.append((url, timeout))
        raise HTTPError(url, 404, "not found", {}, None)

    monkeypatch.setattr("sage.runtime.supervisor.request.urlopen", fake_urlopen)

    wait_for_stack_readiness(
        RuntimeSettings(whisper_provider="whisper_cpp_http"),
        host="127.0.0.1",
        port=8765,
        with_ui=False,
        ui_host="127.0.0.1",
        ui_port=5174,
        timeout_seconds=1,
    )

    assert [call[0] for call in calls] == [
        "http://127.0.0.1:8765/health",
        "http://127.0.0.1:2022/v1",
    ]


def test_start_stack_terminates_children_on_sigterm(monkeypatch):
    class FakeProcess:
        def __init__(self, command, cwd=None):
            self.command = command
            self.cwd = cwd
            self.terminated = False
            self.killed = False
            self.done = False

        def poll(self):
            return 0 if self.done else None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.done = True
            return 0

        def kill(self):
            self.killed = True

    class StopAfterFirstSleep:
        def __init__(self):
            self.handler = None

        def signal(self, signum, handler):
            previous = object()
            if callable(handler):
                self.handler = handler
            return previous

        def sleep(self, seconds):
            assert self.handler is not None
            self.handler(15, None)

    fake_signal = StopAfterFirstSleep()
    processes = []
    monkeypatch.setattr(
        "sage.runtime.supervisor.build_stack_processes",
        lambda *args, **kwargs: [
            type("Spec", (), {"name": "one", "command": ["one"], "cwd": None})(),
            type("Spec", (), {"name": "two", "command": ["two"], "cwd": None})(),
        ],
    )
    monkeypatch.setattr("sage.runtime.supervisor.signal.signal", fake_signal.signal)
    monkeypatch.setattr("sage.runtime.supervisor.time.sleep", fake_signal.sleep)

    def fake_popen(command, cwd=None):
        process = FakeProcess(command, cwd)
        processes.append(process)
        return process

    monkeypatch.setattr("sage.runtime.supervisor.subprocess.Popen", fake_popen)

    exit_code = start_stack(RuntimeSettings(piper_enabled=False), readiness_timeout_seconds=0)

    assert exit_code == 130
    assert [process.terminated for process in processes] == [True, True]
    assert [process.killed for process in processes] == [False, False]
