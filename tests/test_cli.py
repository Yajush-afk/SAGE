from sage import __version__
from sage.cli import main


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

    def fake_request_json(method, url, payload=None):
        calls.append((method, url, payload))
        return 200, {"status": "not_implemented", "transcript": payload["command_text"]}

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    exit_code = main(["text", "start the frontend", "--url", "http://daemon.local"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls == [
        (
            "POST",
            "http://daemon.local/commands/text",
            {"command_text": "start the frontend", "source": "cli_debug"},
        )
    ]
    assert '"transcript": "start the frontend"' in captured.out


def test_cli_health_returns_error_when_daemon_request_fails(monkeypatch, capsys):
    def fake_request_json(method, url, payload=None):
        return 503, {"detail": "unavailable"}

    monkeypatch.setattr("sage.cli.request_json", fake_request_json)

    exit_code = main(["daemon", "health"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert '"detail": "unavailable"' in captured.out
