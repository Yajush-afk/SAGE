from pathlib import Path

from sage.contracts import RuntimeSettings
from sage.tts import NullTTSProvider, PiperTTSProvider


def test_null_tts_returns_success():
    result = NullTTSProvider().speak("Command completed.", RuntimeSettings())

    assert result.success is True
    assert result.provider == "null"


def test_piper_provider_fails_without_voice_path():
    result = PiperTTSProvider().speak("Command completed.", RuntimeSettings())

    assert result.success is False
    assert result.error == "piper_voice_path is not configured"


def test_piper_provider_runs_synthesis_and_playback(monkeypatch, tmp_path):
    voice = tmp_path / "voice.onnx"
    voice.write_text("voice")
    calls = []

    class Completed:
        returncode = 0
        stderr = ""

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if "--output_file" in command:
            output_path = Path(command[command.index("--output_file") + 1])
            output_path.write_bytes(b"wav")
        return Completed()

    monkeypatch.setattr("sage.tts.piper.subprocess.run", fake_run)

    result = PiperTTSProvider().speak(
        "Command completed.",
        RuntimeSettings(piper_voice_path=voice),
    )

    assert result.success is True
    assert calls[0][0][0] == "piper"
    assert calls[1][0][0] == "ffplay"
