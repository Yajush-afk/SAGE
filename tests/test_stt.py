from pathlib import Path
from urllib import error

import pytest

from sage.contracts import RuntimeSettings
from sage.stt import (
    TranscriptionError,
    WhisperCppCliProvider,
    WhisperCppHttpProvider,
    build_stt_provider,
)


def test_build_stt_provider_supports_default_whisper_cpp_http():
    provider = build_stt_provider(RuntimeSettings())

    assert isinstance(provider, WhisperCppHttpProvider)


def test_build_stt_provider_supports_cli():
    provider = build_stt_provider(RuntimeSettings(whisper_provider="whisper_cpp_cli"))

    assert isinstance(provider, WhisperCppCliProvider)


def test_build_stt_provider_rejects_unknown_provider():
    with pytest.raises(TranscriptionError):
        build_stt_provider(RuntimeSettings(whisper_provider="unknown"))


def test_http_provider_extracts_json_text():
    assert WhisperCppHttpProvider._extract_text('{"text": " start frontend "}') == "start frontend"


def test_http_provider_extracts_plain_text():
    assert WhisperCppHttpProvider._extract_text("start frontend") == "start frontend"


def test_http_provider_rejects_empty_response():
    with pytest.raises(TranscriptionError):
        WhisperCppHttpProvider._extract_text("")


def test_http_provider_builds_endpoint_from_base_url():
    endpoint = WhisperCppHttpProvider._transcription_endpoint("http://127.0.0.1:2022/v1")

    assert endpoint == "http://127.0.0.1:2022/v1/audio/transcriptions"


def test_http_provider_transcribes_with_multipart_request(monkeypatch, tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"audio")
    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self):
            return b'{"text": "start frontend"}'

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["content_type"] = req.headers["Content-type"]
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("sage.stt.whisper_cpp.request.urlopen", fake_urlopen)

    result = WhisperCppHttpProvider().transcribe(audio_path, RuntimeSettings())

    assert result.text == "start frontend"
    assert result.provider == "whisper_cpp_http"
    assert captured["url"] == "http://127.0.0.1:2022/v1/audio/transcriptions"
    assert captured["content_type"].startswith("multipart/form-data; boundary=")
    assert captured["timeout"] == 120


def test_http_provider_wraps_connection_failure(monkeypatch, tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"audio")

    def fake_urlopen(req, timeout):
        raise error.URLError("connection refused")

    monkeypatch.setattr("sage.stt.whisper_cpp.request.urlopen", fake_urlopen)

    with pytest.raises(TranscriptionError, match="could not reach Whisper.cpp endpoint"):
        WhisperCppHttpProvider().transcribe(audio_path, RuntimeSettings())


def test_cli_provider_requires_model_path(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"audio")

    with pytest.raises(TranscriptionError, match="whisper_model_path"):
        WhisperCppCliProvider().transcribe(
            audio_path,
            RuntimeSettings(whisper_provider="whisper_cpp_cli"),
        )


def test_cli_provider_parses_stdout(monkeypatch, tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"audio")
    model_path = tmp_path / "model.bin"
    model_path.write_bytes(b"model")

    class Completed:
        returncode = 0
        stdout = "start the frontend\n"
        stderr = ""

    def fake_run(command, capture_output, text, check):
        assert command == [
            "whisper-cli",
            "-m",
            str(model_path),
            "-f",
            str(audio_path),
            "-nt",
        ]
        assert capture_output is True
        assert text is True
        assert check is False
        return Completed()

    monkeypatch.setattr("sage.stt.whisper_cpp.subprocess.run", fake_run)

    result = WhisperCppCliProvider().transcribe(
        Path(audio_path),
        RuntimeSettings(whisper_provider="whisper_cpp_cli", whisper_model_path=model_path),
    )

    assert result.text == "start the frontend"
    assert result.provider == "whisper_cpp_cli"
