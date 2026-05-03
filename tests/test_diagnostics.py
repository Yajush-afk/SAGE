import subprocess
from urllib.error import HTTPError

from sage.contracts import RuntimeSettings
from sage.observability import run_diagnostics


def _mock_binaries(monkeypatch):
    monkeypatch.setattr(
        "sage.observability.diagnostics.shutil.which",
        lambda name: f"/usr/bin/{name}",
    )


def _mock_ollama_models(monkeypatch, output: str):
    monkeypatch.setattr(
        "sage.observability.diagnostics.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, output),
    )


def _reachable_endpoint(*args, **kwargs):
    raise HTTPError("http://127.0.0.1:2022/v1", 404, "not found", {}, None)


def test_diagnostics_mark_piper_requirements_when_enabled(monkeypatch):
    _mock_binaries(monkeypatch)
    _mock_ollama_models(monkeypatch, "gemma4:latest abc 1GB now\n")
    monkeypatch.setattr("sage.observability.diagnostics.request.urlopen", _reachable_endpoint)

    diagnostics = run_diagnostics(RuntimeSettings(piper_enabled=True))
    by_name = {item.name: item for item in diagnostics}

    assert by_name["piper"].required is True
    assert by_name["piper_voice"].required is True


def test_diagnostics_make_piper_optional_when_disabled(monkeypatch):
    _mock_binaries(monkeypatch)
    _mock_ollama_models(monkeypatch, "gemma4:latest abc 1GB now\n")
    monkeypatch.setattr("sage.observability.diagnostics.request.urlopen", _reachable_endpoint)

    diagnostics = run_diagnostics(RuntimeSettings(piper_enabled=False))
    by_name = {item.name: item for item in diagnostics}

    assert by_name["piper"].required is False
    assert by_name["piper_voice"].required is False
    assert by_name["piper_voice"].ok is True


def test_diagnostics_report_missing_configured_whisper_model(monkeypatch, tmp_path):
    _mock_binaries(monkeypatch)
    _mock_ollama_models(monkeypatch, "gemma4:e4b abc 1GB now\n")
    monkeypatch.setattr("sage.observability.diagnostics.request.urlopen", _reachable_endpoint)

    diagnostics = run_diagnostics(
        RuntimeSettings(
            model_name="gemma4:e4b",
            whisper_model_path=tmp_path / "missing.bin",
            piper_enabled=False,
        )
    )
    by_name = {item.name: item for item in diagnostics}

    assert by_name["whisper_model"].required is True
    assert by_name["whisper_model"].ok is False


def test_diagnostics_report_missing_ollama_model(monkeypatch):
    _mock_binaries(monkeypatch)
    _mock_ollama_models(monkeypatch, "gemma4:e2b abc 1GB now\n")
    monkeypatch.setattr("sage.observability.diagnostics.request.urlopen", _reachable_endpoint)

    diagnostics = run_diagnostics(RuntimeSettings(model_name="gemma4:e4b", piper_enabled=False))
    by_name = {item.name: item for item in diagnostics}

    assert by_name["ollama_model"].ok is False
    assert by_name["ollama_model"].detail == "gemma4:e4b not pulled"
