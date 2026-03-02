"""
engram/embeddings.py
Generates embeddings via Ollama (nomic-embed-text) and performs
cosine-similarity search over stored embeddings.
Falls back to full-text search if Ollama is unavailable.
"""

import json
import math
import os
from typing import List, Optional

import requests

OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL = os.environ.get("ENGRAM_EMBED_MODEL", "nomic-embed-text")


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot    = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embed_text(text: str) -> Optional[List[float]]:
    """
    Generate an embedding for `text` using Ollama's local embedding model.
    Returns a list of floats, or None if Ollama is unavailable.
    """
    try:
        resp = requests.post(
            f"{OLLAMA_BASE}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    except Exception:
        return None


def search_similar(query: str, top_k: int = 5) -> List[dict]:
    """
    Embed `query` then rank all stored embeddings by cosine similarity.
    Returns a list of dicts: {command_id, chunk_text, score, timestamp, cwd}.
    Falls back to full-text search if Ollama is unavailable.
    """
    from engram.db import get_all_embeddings, search_fulltext

    query_vec = embed_text(query)

    if query_vec is None:
        # Graceful degradation: fall back to plain text search
        results = search_fulltext(query, limit=top_k)
        for r in results:
            r["score"]      = None
            r["chunk_text"] = r["command"]
        return results

    rows   = get_all_embeddings()
    scored = []
    for row in rows:
        try:
            vec   = json.loads(row["embedding"])
            score = _cosine_similarity(query_vec, vec)
            scored.append({
                "command_id": row["command_id"],
                "chunk_text": row["chunk_text"],
                "score":      score,
                "timestamp":  row["timestamp"],
                "cwd":        row["cwd"],
            })
        except Exception:
            continue

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def index_command(command_id: int, command: str, output: str) -> bool:
    """
    Generate and store an embedding for a command+output pair.
    Returns True on success, False if Ollama was unreachable.
    """
    from engram.db import store_embedding

    chunk = f"Command: {command}\nOutput: {output[:500]}"
    vec   = embed_text(chunk)
    if vec is not None:
        store_embedding(command_id, chunk, vec)
        return True
    return False
