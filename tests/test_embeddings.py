"""tests/test_embeddings.py — Embedding and search tests."""

import json
import pytest
from unittest.mock import patch, MagicMock


def test_cosine_similarity_identical():
    from engram.embeddings import _cosine_similarity
    v = [1.0, 0.0, 0.0]
    assert _cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_opposite():
    from engram.embeddings import _cosine_similarity
    assert _cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_orthogonal():
    from engram.embeddings import _cosine_similarity
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector():
    from engram.embeddings import _cosine_similarity
    assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_embed_text_success():
    from engram.embeddings import embed_text
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
    mock_resp.raise_for_status = MagicMock()
    with patch("requests.post", return_value=mock_resp):
        result = embed_text("hello world")
    assert result == [0.1, 0.2, 0.3]


def test_embed_text_returns_none_on_connection_error():
    from engram.embeddings import embed_text
    with patch("requests.post", side_effect=ConnectionError("refused")):
        assert embed_text("hello") is None


def test_embed_text_returns_none_on_timeout():
    from engram.embeddings import embed_text
    import requests as req
    with patch("requests.post", side_effect=req.exceptions.Timeout()):
        assert embed_text("hello") is None


def test_index_command_returns_true_on_success(monkeypatch, tmp_path):
    monkeypatch.setenv("ENGRAM_DIR", str(tmp_path))
    import importlib, engram.db as db_mod, engram.embeddings as emb_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    importlib.reload(emb_mod)

    row_id = db_mod.log_command("echo hi", "hi", 0, "/", "s")
    with patch.object(emb_mod, "embed_text", return_value=[0.1, 0.2]):
        result = emb_mod.index_command(row_id, "echo hi", "hi")
    assert result is True

    importlib.reload(db_mod)


def test_index_command_returns_false_when_ollama_down(monkeypatch, tmp_path):
    monkeypatch.setenv("ENGRAM_DIR", str(tmp_path))
    import importlib, engram.db as db_mod, engram.embeddings as emb_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    importlib.reload(emb_mod)

    row_id = db_mod.log_command("echo hi", "hi", 0, "/", "s")
    with patch.object(emb_mod, "embed_text", return_value=None):
        result = emb_mod.index_command(row_id, "echo hi", "hi")
    assert result is False

    importlib.reload(db_mod)


def test_search_similar_fallback_to_fulltext(monkeypatch, tmp_path):
    monkeypatch.setenv("ENGRAM_DIR", str(tmp_path))
    import importlib, engram.db as db_mod, engram.embeddings as emb_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    importlib.reload(emb_mod)

    db_mod.log_command("docker build .", "error: no dockerfile", 1, "/", "s")

    with patch.object(emb_mod, "embed_text", return_value=None):
        results = emb_mod.search_similar("docker", top_k=5)

    assert len(results) >= 1
    assert results[0]["command"] == "docker build ."

    importlib.reload(db_mod)


def test_search_similar_vector_ranking(monkeypatch, tmp_path):
    monkeypatch.setenv("ENGRAM_DIR", str(tmp_path))
    import importlib, engram.db as db_mod, engram.embeddings as emb_mod
    importlib.reload(db_mod)
    db_mod.init_db()
    importlib.reload(emb_mod)

    r1 = db_mod.log_command("docker build", "err", 1, "/", "s")
    r2 = db_mod.log_command("ls -la",       "ok",  0, "/", "s")

    # Store embeddings manually
    db_mod.store_embedding(r1, "Command: docker build\nOutput: err", [1.0, 0.0])
    db_mod.store_embedding(r2, "Command: ls -la\nOutput: ok",        [0.0, 1.0])

    # Query vector close to r1
    with patch.object(emb_mod, "embed_text", return_value=[0.99, 0.01]):
        results = emb_mod.search_similar("docker error", top_k=2)

    assert results[0]["command_id"] == r1
    assert results[1]["command_id"] == r2

    importlib.reload(db_mod)
