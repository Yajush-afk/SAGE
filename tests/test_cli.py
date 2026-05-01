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
