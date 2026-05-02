from sage.contracts import RuntimeSettings
from sage.observability import run_diagnostics


def test_diagnostics_mark_piper_requirements_when_enabled():
    diagnostics = run_diagnostics(RuntimeSettings(piper_enabled=True))
    by_name = {item.name: item for item in diagnostics}

    assert by_name["piper"].required is True
    assert by_name["piper_voice"].required is True


def test_diagnostics_make_piper_optional_when_disabled():
    diagnostics = run_diagnostics(RuntimeSettings(piper_enabled=False))
    by_name = {item.name: item for item in diagnostics}

    assert by_name["piper"].required is False
    assert by_name["piper_voice"].required is False
    assert by_name["piper_voice"].ok is True
