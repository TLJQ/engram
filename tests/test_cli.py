"""tests/test_cli.py — CLI integration tests."""

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner  # We'll use argparse directly instead


@pytest.fixture(autouse=True)
def tmp_engram(monkeypatch, tmp_path):
    monkeypatch.setenv("ENGRAM_DIR", str(tmp_path))
    import importlib, engram.db as m
    importlib.reload(m)
    m.init_db()
    yield
    importlib.reload(m)


def run_cli(args: list[str]) -> tuple[int, str]:
    """Run the engram CLI and capture stdout."""
    import io, sys
    from engram.cli import main

    old_argv = sys.argv
    old_stdout = sys.stdout
    sys.argv = ["engram"] + args
    sys.stdout = io.StringIO()

    exit_code = 0
    try:
        main()
    except SystemExit as e:
        exit_code = e.code or 0
    finally:
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        sys.argv = old_argv

    return exit_code, output


def test_no_args_shows_help():
    code, out = run_cli([])
    assert "engram" in out.lower() or code == 0


def test_history_empty():
    code, out = run_cli(["history"])
    assert "No history" in out


def test_search_empty():
    code, out = run_cli(["search", "docker"])
    assert "No results" in out


def test_log_and_history():
    from engram.embeddings import index_command as real_idx
    with patch("engram.embeddings.embed_text", return_value=None):
        run_cli([
            "log",
            "--command", "git status",
            "--output", "On branch main",
            "--exit-code", "0",
            "--cwd", "/home/user/project",
            "--session", "test-session",
        ])

    code, out = run_cli(["history"])
    assert "git status" in out


def test_log_skips_sensitive_command():
    from engram.db import get_recent_commands
    with patch("engram.embeddings.embed_text", return_value=None):
        run_cli([
            "log",
            "--command", "sudo passwd alice",
            "--output", "",
            "--exit-code", "0",
            "--cwd", "/",
            "--session", "s",
        ])
    rows = get_recent_commands()
    assert len(rows) == 0


def test_log_redacts_secret():
    from engram.db import get_recent_commands
    with patch("engram.embeddings.embed_text", return_value=None):
        run_cli([
            "log",
            "--command", "export API_KEY=topsecret12345",
            "--output", "",
            "--exit-code", "0",
            "--cwd", "/",
            "--session", "s",
        ])
    rows = get_recent_commands()
    assert len(rows) == 1
    assert "topsecret12345" not in rows[0]["command"]


def test_search_finds_result():
    with patch("engram.embeddings.embed_text", return_value=None):
        run_cli([
            "log", "--command", "docker build .",
            "--output", "Error: no dockerfile",
            "--exit-code", "1", "--cwd", "/app", "--session", "s",
        ])

    code, out = run_cli(["search", "docker"])
    assert "docker build" in out


def test_status_shows_counts():
    with patch("requests.get", side_effect=Exception("no ollama")):
        code, out = run_cli(["status"])
    assert "Commands" in out
    assert "DB path" in out


def test_clear_with_yes_flag():
    with patch("engram.embeddings.embed_text", return_value=None):
        run_cli([
            "log", "--command", "ls", "--output", "file.txt",
            "--exit-code", "0", "--cwd", "/", "--session", "s",
        ])

    from engram.db import get_recent_commands
    assert len(get_recent_commands()) == 1

    run_cli(["clear", "--yes"])
    assert len(get_recent_commands()) == 0


def test_index_no_commands():
    code, out = run_cli(["index"])
    assert "already indexed" in out or "0" in out
