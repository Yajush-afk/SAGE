import json

from sage import __version__
from sage.cli import main, request_json


def test_cli_help(capsys):
    exit_code = main([])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "SAGE local-first voice command layer" in captured.out


def test_cli_version(capsys):
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0

    captured = capsys.readouterr()

    assert f"sage {__version__}" in captured.out


def test_cli_text_posts_to_daemon(monkeypatch, capsys):
    calls = []

    def fake_request_json(method, url, payload=None, *, timeout_seconds=5):
        calls.append((method, url, payload, timeout_seconds))
        return 200, {"status": "not_implemented", "transcript": payload["command_text"]}

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    exit_code = main(["text", "start the frontend", "--url", "http://daemon.local"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [
        (
            "POST",
            "http://daemon.local/commands/text",
            {
                "command_text": "start the frontend",
                "source": "cli_debug",
                "cwd": "/home/yajush-afk/my_repo/SAGE",
            },
            300,
        )
    ]
    assert '"transcript": "start the frontend"' in captured.out


def test_cli_listen_once_uses_long_timeout(monkeypatch, capsys):
    calls = []

    def fake_request_json(method, url, payload=None, *, timeout_seconds=5):
        calls.append((method, url, payload, timeout_seconds))
        return 200, {"status": "completed"}

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    exit_code = main(["listen-once", "--url", "http://daemon.local"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [("POST", "http://daemon.local/commands/listen-once", None, 300)]
    assert '"status": "completed"' in captured.out


def test_cli_listen_once_allows_timeout_override(monkeypatch):
    calls = []

    def fake_request_json(method, url, payload=None, *, timeout_seconds=5):
        calls.append(timeout_seconds)
        return 200, {"status": "completed"}

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    assert main(["listen-once", "--timeout", "30"]) == 0
    assert calls == [30]


def test_cli_health_returns_error_when_daemon_request_fails(monkeypatch, capsys):
    def fake_request_json(method, url, payload=None):
        return 503, {"detail": "unavailable"}

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    exit_code = main(["daemon", "health"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert '"detail": "unavailable"' in captured.out


def test_request_json_converts_timeout_to_runtime_error(monkeypatch):
    def fake_urlopen(req, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr("sage.cli.request.urlopen", fake_urlopen)

    try:
        request_json("GET", "http://daemon.local/slow", timeout_seconds=7)
    except RuntimeError as exc:
        assert str(exc) == "SAGE daemon request timed out after 7 seconds"
    else:
        raise AssertionError("expected RuntimeError")


def test_cli_commands_show_gets_command(monkeypatch, capsys):
    calls = []

    def fake_request_json(method, url, payload=None):
        calls.append((method, url, payload))
        return 200, {"id": "cmd_123", "status": "completed"}

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    exit_code = main(
        [
            "commands",
            "show",
            "cmd_123",
            "--url",
            "http://daemon.local",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [("GET", "http://daemon.local/commands/cmd_123", None)]
    assert '"id": "cmd_123"' in captured.out


def test_cli_commands_show_returns_failure_for_missing_command(monkeypatch, capsys):
    def fake_request_json(method, url, payload=None):
        return 404, {"detail": "Command not found."}

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    exit_code = main(["commands", "show", "missing", "--url", "http://daemon.local"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert '"detail": "Command not found."' in captured.out


def test_cli_confirm_posts_confirmation_phrase(monkeypatch, capsys):
    calls = []

    def fake_request_json(method, url, payload=None):
        calls.append((method, url, payload))
        return 200, {"status": "confirmed"}

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    exit_code = main(
        [
            "commands",
            "confirm",
            "cmd_123",
            "confirm start",
            "--url",
            "http://daemon.local",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [
        (
            "POST",
            "http://daemon.local/commands/cmd_123/confirm",
            {"phrase": "confirm start"},
        )
    ]
    assert '"status": "confirmed"' in captured.out


def test_cli_cancel_posts_cancel_request(monkeypatch, capsys):
    calls = []

    def fake_request_json(method, url, payload=None):
        calls.append((method, url, payload))
        return 200, {"status": "cancelled"}

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    exit_code = main(["commands", "cancel", "cmd_123", "--url", "http://daemon.local"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [("POST", "http://daemon.local/commands/cmd_123/cancel", None)]
    assert '"status": "cancelled"' in captured.out


def test_cli_workflows_show_gets_workflow(monkeypatch, capsys):
    calls = []

    def fake_request_json(method, url, payload=None, *, timeout_seconds=5):
        calls.append((method, url, payload, timeout_seconds))
        return 200, {"id": "wf_123", "name": "inspect"}

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    exit_code = main(["workflows", "show", "inspect", "--url", "http://daemon.local"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [("GET", "http://daemon.local/workflows/inspect", None, 5)]
    assert '"name": "inspect"' in captured.out


def test_cli_workflows_run_posts_workflow_run(monkeypatch, tmp_path, capsys):
    calls = []

    def fake_request_json(method, url, payload=None, *, timeout_seconds=5):
        calls.append((method, url, payload, timeout_seconds))
        return 200, {"status": "completed", "transcript": "workflow: inspect"}

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    exit_code = main(
        [
            "workflows",
            "run",
            "inspect",
            "--cwd",
            str(tmp_path),
            "--timeout",
            "45",
            "--url",
            "http://daemon.local",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [
        (
            "POST",
            "http://daemon.local/workflows/inspect/run",
            {"cwd": str(tmp_path.resolve())},
            45,
        )
    ]
    assert '"workflow: inspect"' in captured.out


def test_cli_workflows_delete_deletes_workflow(monkeypatch, capsys):
    calls = []

    def fake_request_json(method, url, payload=None, *, timeout_seconds=5):
        calls.append((method, url, payload, timeout_seconds))
        return 200, {"deleted": True}

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    exit_code = main(["workflows", "delete", "inspect", "--url", "http://daemon.local"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [("DELETE", "http://daemon.local/workflows/inspect", None, 5)]
    assert '"deleted": true' in captured.out


def test_cli_start_runs_local_stack(monkeypatch):
    calls = []

    def fake_start_stack(settings, **kwargs):
        calls.append((settings, kwargs))
        return 0

    monkeypatch.setattr("sage.cli.load_runtime_settings", lambda: object())
    monkeypatch.setattr("sage.cli.start_stack", fake_start_stack)

    exit_code = main(["start", "--with-ui", "--port", "9999"])

    assert exit_code == 0
    assert calls[0][1]["host"] == "127.0.0.1"
    assert calls[0][1]["port"] == 9999
    assert calls[0][1]["with_ui"] is True
    assert calls[0][1]["ui_host"] == "127.0.0.1"
    assert calls[0][1]["ui_port"] == 5174


def test_cli_profile_show_reads_daemon_profile(monkeypatch, capsys):
    calls = []

    def fake_request_json(method, url, payload=None, *, timeout_seconds=5):
        calls.append((method, url, payload))
        return 200, {"assistant_name": "SAGE"}

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    exit_code = main(["profile", "show", "--url", "http://daemon.local"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [("GET", "http://daemon.local/profile", None)]
    assert '"assistant_name": "SAGE"' in captured.out


def test_cli_profile_set_updates_editable_fields(monkeypatch):
    calls = []

    def fake_request_json(method, url, payload=None, *, timeout_seconds=5):
        calls.append((method, url, payload))
        return 200, payload

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    exit_code = main(
        [
            "profile",
            "set",
            "--assistant-name",
            "Laptop Sage",
            "--user-name",
            "Yajush",
            "--url",
            "http://daemon.local",
        ]
    )

    assert exit_code == 0
    assert calls == [
        (
            "PUT",
            "http://daemon.local/profile",
            {"assistant_name": "Laptop Sage", "user_display_name": "Yajush"},
        )
    ]


def test_cli_doctor_returns_failure_when_required_check_fails(monkeypatch, capsys):
    class Diagnostic:
        def __init__(self, ok, required):
            self.ok = ok
            self.required = required
            self.severity = "error" if not ok and required else "ok"
            self.name = "ollama"
            self.detail = "missing"
            self.fix_hint = "Install Ollama."
            self.docs_anchor = "docs/local-setup.md#ollama"

        def model_dump(self):
            return {
                "name": self.name,
                "ok": self.ok,
                "required": self.required,
                "detail": self.detail,
                "severity": self.severity,
                "fix_hint": self.fix_hint,
                "docs_anchor": self.docs_anchor,
            }

    monkeypatch.setattr("sage.cli.load_runtime_settings", lambda: object())
    monkeypatch.setattr("sage.cli.run_diagnostics", lambda settings: [Diagnostic(False, True)])

    exit_code = main(["doctor"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "[FAIL] ollama (required)" in captured.out
    assert "fix: Install Ollama." in captured.out
    assert "1 required check(s) failed." in captured.out


def test_cli_doctor_json_prints_raw_diagnostics(monkeypatch, capsys):
    class Diagnostic:
        ok = False
        required = True
        severity = "error"
        name = "ollama"
        detail = "missing"
        fix_hint = "Install Ollama."
        docs_anchor = "docs/local-setup.md#ollama"

        def model_dump(self):
            return {
                "name": self.name,
                "ok": self.ok,
                "required": self.required,
                "detail": self.detail,
                "severity": self.severity,
                "fix_hint": self.fix_hint,
                "docs_anchor": self.docs_anchor,
            }

    monkeypatch.setattr("sage.cli.load_runtime_settings", lambda: object())
    monkeypatch.setattr("sage.cli.run_diagnostics", lambda settings: [Diagnostic()])

    exit_code = main(["doctor", "--json"])

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)

    assert exit_code == 1
    assert parsed == [
        {
            "name": "ollama",
            "ok": False,
            "required": True,
            "detail": "missing",
            "severity": "error",
            "fix_hint": "Install Ollama.",
            "docs_anchor": "docs/local-setup.md#ollama",
        }
    ]
