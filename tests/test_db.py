"""tests/test_db.py — Database layer tests."""

import pytest


@pytest.fixture(autouse=True)
def tmp_engram(monkeypatch, tmp_path):
    monkeypatch.setenv("ENGRAM_DIR", str(tmp_path))
    import importlib, engram.db as m
    importlib.reload(m)
    m.init_db()
    yield
    importlib.reload(m)


def test_log_returns_id():
    from engram.db import log_command
    row_id = log_command("echo hi", "hi", 0, "/tmp", "s1")
    assert isinstance(row_id, int)
    assert row_id > 0


def test_log_and_retrieve():
    from engram.db import log_command, get_recent_commands
    log_command("echo hello", "hello", 0, "/tmp", "s1")
    rows = get_recent_commands(limit=10)
    assert len(rows) == 1
    assert rows[0]["command"] == "echo hello"
    assert rows[0]["output"]  == "hello"
    assert rows[0]["exit_code"] == 0


def test_multiple_ids_are_unique():
    from engram.db import log_command
    id1 = log_command("cmd1", "out1", 0, "/", "s")
    id2 = log_command("cmd2", "out2", 0, "/", "s")
    assert id1 != id2
    assert id2 > id1


def test_search_fulltext_command():
    from engram.db import log_command, search_fulltext
    log_command("docker build .", "Error: missing Dockerfile", 1, "/project", "s1")
    log_command("ls -la", "total 0", 0, "/home", "s1")

    results = search_fulltext("docker")
    assert len(results) == 1
    assert "docker" in results[0]["command"]


def test_search_fulltext_output():
    from engram.db import log_command, search_fulltext
    log_command("curl api.example.com", '{"error": "unauthorized"}', 1, "/", "s")
    results = search_fulltext("unauthorized")
    assert len(results) == 1


def test_search_no_results():
    from engram.db import log_command, search_fulltext
    log_command("ls", "file.txt", 0, "/", "s")
    assert search_fulltext("zzznothingzzz") == []


def test_recent_commands_ordering():
    from engram.db import log_command, get_recent_commands
    for i in range(5):
        log_command(f"cmd{i}", f"out{i}", 0, "/", "s")
    rows = get_recent_commands(limit=10)
    assert rows[0]["command"] == "cmd4"  # most recent first
    assert rows[4]["command"] == "cmd0"


def test_store_and_get_embedding():
    from engram.db import log_command, store_embedding, get_all_embeddings
    row_id = log_command("curl api", '{"ok": true}', 0, "/", "s")
    store_embedding(row_id, "curl api\n{ok: true}", [0.1, 0.2, 0.3])
    embs = get_all_embeddings()
    assert len(embs) == 1
    assert embs[0]["command_id"] == row_id


def test_get_command_by_id():
    from engram.db import log_command, get_command_by_id
    row_id = log_command("whoami", "alice", 0, "/home/alice", "s")
    row = get_command_by_id(row_id)
    assert row["command"] == "whoami"
    assert row["cwd"]     == "/home/alice"


def test_get_command_by_id_missing():
    from engram.db import get_command_by_id
    assert get_command_by_id(99999) is None
