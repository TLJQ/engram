"""
engram/db.py
Handles all SQLite storage: commands, outputs, and vector embeddings.
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

ENGRAM_DIR = Path(os.environ.get("ENGRAM_DIR", Path.home() / ".engram"))
DB_PATH    = ENGRAM_DIR / "engram.db"


def get_connection() -> sqlite3.Connection:
    ENGRAM_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables and indexes if they don't already exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS commands (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            command     TEXT    NOT NULL,
            output      TEXT,
            exit_code   INTEGER,
            cwd         TEXT,
            session_id  TEXT
        );

        CREATE TABLE IF NOT EXISTS embeddings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            command_id  INTEGER NOT NULL REFERENCES commands(id) ON DELETE CASCADE,
            embedding   TEXT    NOT NULL,   -- JSON-serialized float list
            chunk_text  TEXT    NOT NULL    -- the text that was embedded
        );

        CREATE INDEX IF NOT EXISTS idx_commands_timestamp ON commands(timestamp);
        CREATE INDEX IF NOT EXISTS idx_commands_session   ON commands(session_id);
        CREATE INDEX IF NOT EXISTS idx_embeddings_cmd     ON embeddings(command_id);
    """)
    conn.commit()
    conn.close()


def log_command(
    command:    str,
    output:     str,
    exit_code:  int,
    cwd:        str,
    session_id: str,
    timestamp:  Optional[str] = None,
) -> int:
    """
    Insert one command+output record into the DB.
    Returns the new row's id (always > 0).
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    conn = get_connection()
    cur  = conn.execute(
        """
        INSERT INTO commands (timestamp, command, output, exit_code, cwd, session_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (timestamp, command, output, exit_code, cwd, session_id),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id  # type: ignore[return-value]


def get_recent_commands(limit: int = 200) -> List[Dict[str, Any]]:
    """Return the N most recent command rows, newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM commands ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_fulltext(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Case-insensitive LIKE search across command text and output."""
    conn    = get_connection()
    pattern = f"%{query}%"
    rows    = conn.execute(
        """
        SELECT * FROM commands
        WHERE command LIKE ? OR output LIKE ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (pattern, pattern, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def store_embedding(command_id: int, chunk_text: str, embedding: List[float]) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO embeddings (command_id, chunk_text, embedding) VALUES (?, ?, ?)",
        (command_id, chunk_text, json.dumps(embedding)),
    )
    conn.commit()
    conn.close()


def get_all_embeddings() -> List[Dict[str, Any]]:
    """Return every stored embedding joined with its command's metadata."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT e.id, e.command_id, e.chunk_text, e.embedding,
               c.timestamp, c.cwd
        FROM   embeddings e
        JOIN   commands   c ON e.command_id = c.id
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_command_by_id(command_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM commands WHERE id = ?", (command_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
