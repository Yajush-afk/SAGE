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
    assert by_name["whisper_model"].severity == "error"
    assert "whisper_model_path" in by_name["whisper_model"].fix_hint


def test_diagnostics_report_missing_ollama_model(monkeypatch):
    _mock_binaries(monkeypatch)
    _mock_ollama_models(monkeypatch, "gemma4:e2b abc 1GB now\n")
    monkeypatch.setattr("sage.observability.diagnostics.request.urlopen", _reachable_endpoint)

    diagnostics = run_diagnostics(RuntimeSettings(model_name="gemma4:e4b", piper_enabled=False))
    by_name = {item.name: item for item in diagnostics}

    assert by_name["ollama_model"].ok is False
    assert by_name["ollama_model"].detail == "gemma4:e4b not pulled"
    assert by_name["ollama_model"].severity == "error"
    assert by_name["ollama_model"].fix_hint == "Run `ollama pull gemma4:e4b`."


def test_diagnostics_warn_for_heavy_ollama_resource_profile(monkeypatch):
    _mock_binaries(monkeypatch)
    _mock_ollama_models(monkeypatch, "gemma4:e4b abc 9.6GB now\n")
    monkeypatch.setattr("sage.observability.diagnostics.request.urlopen", _reachable_endpoint)

    diagnostics = run_diagnostics(
        RuntimeSettings(
            model_name="gemma4:e4b",
            ollama_num_ctx=4096,
            ollama_keep_alive="5m",
            piper_enabled=False,
        )
    )
    by_name = {item.name: item for item in diagnostics}

    assert by_name["ollama_resource_profile"].ok is False
    assert by_name["ollama_resource_profile"].severity == "warning"
    assert "qwen2.5:3b" in by_name["ollama_resource_profile"].fix_hint


def test_diagnostics_accept_lightweight_ollama_resource_profile(monkeypatch):
    _mock_binaries(monkeypatch)
    _mock_ollama_models(monkeypatch, "qwen2.5:3b abc 2GB now\n")
    monkeypatch.setattr("sage.observability.diagnostics.request.urlopen", _reachable_endpoint)

    diagnostics = run_diagnostics(
        RuntimeSettings(
            model_name="qwen2.5:3b",
            ollama_num_ctx=2048,
            ollama_keep_alive="30s",
            piper_enabled=False,
        )
    )
    by_name = {item.name: item for item in diagnostics}

    assert by_name["ollama_resource_profile"].ok is True
    assert by_name["ollama_resource_profile"].severity == "ok"


def test_diagnostics_blocks_unimplemented_custom_planner_provider(monkeypatch):
    _mock_binaries(monkeypatch)
    _mock_ollama_models(monkeypatch, "gemma4:latest abc 1GB now\n")
    monkeypatch.setattr("sage.observability.diagnostics.request.urlopen", _reachable_endpoint)

    diagnostics = run_diagnostics(
        RuntimeSettings(planner_provider="custom_http", piper_enabled=False)
    )
    by_name = {item.name: item for item in diagnostics}

    assert by_name["planner_provider"].ok is False
    assert by_name["planner_provider"].severity == "error"
    assert "not implemented yet" in by_name["planner_provider"].detail


def test_diagnostics_include_fix_hint_for_unreachable_whisper_endpoint(monkeypatch):
    _mock_binaries(monkeypatch)
    _mock_ollama_models(monkeypatch, "gemma4:latest abc 1GB now\n")

    def unreachable(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr("sage.observability.diagnostics.request.urlopen", unreachable)

    diagnostics = run_diagnostics(RuntimeSettings(piper_enabled=False))
    by_name = {item.name: item for item in diagnostics}

    assert by_name["whisper_endpoint"].ok is False
    assert by_name["whisper_endpoint"].severity == "error"
    assert "whisper-server" in by_name["whisper_endpoint"].fix_hint
    assert by_name["whisper_endpoint"].docs_anchor == "docs/local-setup.md#whispercpp"
