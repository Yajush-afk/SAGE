from sage.audio import AudioRecordingError, FfmpegAudioRecorder
from sage.contracts import RuntimeSettings


def test_ffmpeg_recorder_builds_bounded_recording_command(monkeypatch, tmp_path):
    output_files = []

    class Completed:
        returncode = 0
        stderr = ""

    def fake_run(command, capture_output, text, check):
        output_path = command[-1]
        output_files.append(output_path)
        with open(output_path, "wb") as audio_file:
            audio_file.write(b"audio")
        assert command[:7] == [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "pulse",
        ]
        assert "-t" in command
        assert "3" in command
        assert capture_output is True
        assert text is True
        assert check is False
        return Completed()

    monkeypatch.setattr("sage.audio.recorder.subprocess.run", fake_run)

    recording = FfmpegAudioRecorder().record_once(
        RuntimeSettings(
            max_recording_seconds=3,
            audio_cache_dir=tmp_path,
            audio_sample_rate_hz=16000,
            audio_channels=1,
        )
    )

    assert recording.path.exists()
    assert str(recording.path) == output_files[0]
    assert recording.sample_rate_hz == 16000
    assert recording.channels == 1


def test_ffmpeg_recorder_raises_on_failed_process(monkeypatch, tmp_path):
    class Completed:
        returncode = 1
        stderr = "no input device"

    def fake_run(command, capture_output, text, check):
        return Completed()

    monkeypatch.setattr("sage.audio.recorder.subprocess.run", fake_run)

    try:
        FfmpegAudioRecorder().record_once(RuntimeSettings(audio_cache_dir=tmp_path))
    except AudioRecordingError as exc:
        assert "no input device" in str(exc)
    else:
        raise AssertionError("expected AudioRecordingError")
