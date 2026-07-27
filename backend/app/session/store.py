"""Session store: SQLite-backed persistence for chat sessions.

Replaces the previous JSON-file store. The whole database lives in a single
file (backend/data/chat.db): no server, no accounts, no extra dependencies --
sqlite3 ships with the Python standard library. All public functions keep the
same signatures and return shapes as the old implementation, so callers
(app/main.py) need no changes.

On first init, any legacy per-session JSON files under data/sessions/ are
imported into the database automatically, so existing data is preserved.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = DATA_DIR / "chat.db"

# Legacy JSON store; kept only as a migration source. Left in place after
# migration as a backup -- safe to delete manually once the DB looks good.
SESSIONS_DIR = DATA_DIR / "sessions"

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

# Top-level session keys that get dedicated columns; anything else is tucked
# into the `extra` JSON column so update_session's "merge anything" behavior
# from the JSON era is preserved.
_COLUMN_FIELDS = {"title", "status"}
_RESERVED_FIELDS = {"id", "messages", "created_at", "updated_at", "metadata"}


def _now_iso() -> str:
    return datetime.now().isoformat()


def _db() -> sqlite3.Connection:
    """Lazily create the shared connection, schema, and run JSON migration."""
    global _conn
    if _conn is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id         TEXT PRIMARY KEY,
                title      TEXT NOT NULL DEFAULT '新对话',
                status     TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata   TEXT NOT NULL DEFAULT '{}',
                extra      TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS messages (
                id         TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL DEFAULT '',
                timestamp  INTEGER NOT NULL,
                steps      TEXT NOT NULL DEFAULT '[]',
                seq        INTEGER NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, seq);
            CREATE TABLE IF NOT EXISTS memories (
                id         TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL DEFAULT 'default',
                key        TEXT NOT NULL,
                content    TEXT NOT NULL,
                category   TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, key)
            );
            """
        )
        conn.commit()
        _migrate_from_json(conn)
        _conn = conn
    return _conn


def _row_to_message(m: sqlite3.Row) -> dict:
    return {
        "id": m["id"],
        "role": m["role"],
        "content": m["content"],
        "timestamp": m["timestamp"],
        "steps": json.loads(m["steps"] or "[]"),
    }


def _session_from_row(row: sqlite3.Row, messages: list[dict]) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "messages": messages,
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "metadata": json.loads(row["metadata"] or "{}"),
        # surface any non-standard persisted keys at the top level
        **json.loads(row["extra"] or "{}"),
    }


def create_session(session_id: str) -> dict:
    """Create a new empty session. No-op if the id already exists."""
    now = _now_iso()
    with _lock:
        db = _db()
        db.execute(
            "INSERT OR IGNORE INTO sessions "
            "(id, title, status, created_at, updated_at, metadata, extra) "
            "VALUES (?, '新对话', NULL, ?, ?, '{}', '{}')",
            (session_id, now, now),
        )
        db.commit()
    return {
        "id": session_id,
        "title": "新对话",
        "messages": [],
        "status": None,
        "created_at": now,
        "updated_at": now,
        "metadata": {},
    }


def get_session(session_id: str) -> dict | None:
    """Return a full session dict, or None if not found."""
    with _lock:
        db = _db()
        row = db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        msg_rows = db.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY seq ASC",
            (session_id,),
        ).fetchall()
        messages = [_row_to_message(m) for m in msg_rows]
    return _session_from_row(row, messages)


def get_or_create(session_id: str) -> dict:
    """Return existing session or create a new one."""
    session = get_session(session_id)
    if session is None:
        session = create_session(session_id)
    return session


def list_sessions() -> list[dict]:
    """List all sessions (without messages) sorted by updated_at desc."""
    with _lock:
        db = _db()
        rows = db.execute(
            "SELECT s.id, s.title, s.status, s.created_at, s.updated_at, s.extra, "
            "(SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) "
            "AS message_count "
            "FROM sessions s "
            "ORDER BY s.updated_at DESC"
        ).fetchall()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "status": r["status"],
            "updated_at": r["updated_at"],
            "created_at": r["created_at"],
            "message_count": r["message_count"],
        }
        for r in rows
    ]


def delete_session(session_id: str) -> bool:
    """Delete a session (and its messages via cascade). Returns True if deleted."""
    with _lock:
        db = _db()
        cur = db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        db.commit()
        return cur.rowcount > 0


def append_message(session_id: str, message: dict) -> dict | None:
    """Append a message to a session."""
    with _lock:
        db = _db()
        if db.execute(
            "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
        ).fetchone() is None:
            return None
        seq = (
            db.execute(
                "SELECT COALESCE(MAX(seq), -1) AS m FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()["m"]
            + 1
        )
        db.execute(
            "INSERT INTO messages "
            "(id, session_id, role, content, timestamp, steps, seq) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                message.get("id") or f"msg-{int(datetime.now().timestamp())}",
                session_id,
                message.get("role", "user"),
                message.get("content", ""),
                message.get("timestamp", 0),
                json.dumps(message.get("steps", []), ensure_ascii=False),
                seq,
            ),
        )
        db.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (_now_iso(), session_id),
        )
        db.commit()
    return get_session(session_id)


def update_session(session_id: str, updates: dict[str, Any]) -> dict | None:
    """Merge updates into a session.

    `title`/`status` go to dedicated columns; `metadata` replaces the metadata
    blob; any other key is stored in the `extra` JSON column, mirroring the old
    "merge anything" behavior. id/messages/timestamps are never overwritten here.
    """
    with _lock:
        db = _db()
        if db.execute(
            "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
        ).fetchone() is None:
            return None

        sets: list[str] = []
        args: list[Any] = []
        extra = json.loads(
            db.execute(
                "SELECT extra FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()["extra"]
            or "{}"
        )
        for key, val in updates.items():
            if key in _RESERVED_FIELDS:
                continue
            if key in _COLUMN_FIELDS:
                sets.append(f"{key} = ?")
                args.append(val)
            elif key == "metadata":
                sets.append("metadata = ?")
                args.append(json.dumps(val, ensure_ascii=False))
            else:
                extra[key] = val
        if extra:
            sets.append("extra = ?")
            args.append(json.dumps(extra, ensure_ascii=False))
        sets.append("updated_at = ?")
        args.append(_now_iso())
        args.append(session_id)
        db.execute(
            f"UPDATE sessions SET {', '.join(sets)} WHERE id = ?", args
        )
        db.commit()
    return get_session(session_id)


def update_metadata(session_id: str, metadata: dict[str, Any]) -> dict | None:
    """Merge metadata fields into session.metadata."""
    with _lock:
        db = _db()
        row = db.execute(
            "SELECT metadata FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        current = json.loads(row["metadata"] or "{}")
        current.update(metadata)
        db.execute(
            "UPDATE sessions SET metadata = ?, updated_at = ? WHERE id = ?",
            (json.dumps(current, ensure_ascii=False), _now_iso(), session_id),
        )
        db.commit()
    return get_session(session_id)


def derive_title(message: str) -> str:
    """Derive a session title from the first user message."""
    text = message.strip()
    return text[:20] + "..." if len(text) > 20 else text


def _import_session(db: sqlite3.Connection, s: dict) -> None:
    """Import one legacy session dict into the database."""
    sid = s["id"]
    standard = _RESERVED_FIELDS | _COLUMN_FIELDS
    extra = {k: v for k, v in s.items() if k not in standard}
    db.execute(
        "INSERT OR IGNORE INTO sessions "
        "(id, title, status, created_at, updated_at, metadata, extra) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            sid,
            s.get("title", "新对话"),
            s.get("status"),
            s.get("created_at", _now_iso()),
            s.get("updated_at", _now_iso()),
            json.dumps(s.get("metadata", {}), ensure_ascii=False),
            json.dumps(extra, ensure_ascii=False),
        ),
    )
    for seq, m in enumerate(s.get("messages", [])):
        db.execute(
            "INSERT OR IGNORE INTO messages "
            "(id, session_id, role, content, timestamp, steps, seq) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                m.get("id") or f"msg-{sid}-{seq}",
                sid,
                m.get("role", "user"),
                m.get("content", ""),
                m.get("timestamp", 0),
                json.dumps(m.get("steps", []), ensure_ascii=False),
                seq,
            ),
        )


def _migrate_from_json(db: sqlite3.Connection) -> None:
    """One-time import of legacy per-session JSON files, if present."""
    if not SESSIONS_DIR.exists():
        return
    for path in SESSIONS_DIR.glob("*.json"):
        try:
            s = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not s.get("id"):
            continue
        # Skip sessions already present in the DB.
        if db.execute(
            "SELECT 1 FROM sessions WHERE id = ?", (s["id"],)
        ).fetchone():
            continue
        _import_session(db, s)
    db.commit()


# ---------------------------------------------------------------------------
# Long-term memory: per-user facts (preferences, corrections, context)
# extracted from conversations. Stored in the `memories` table.
# ---------------------------------------------------------------------------

DEFAULT_USER_ID = "default"


def upsert_memory(user_id, key, content, category=None):
    """Insert or update a memory keyed by (user_id, key)."""
    now = _now_iso()
    mem_id = f"{user_id}:{key}"
    with _lock:
        db = _db()
        db.execute(
            "INSERT INTO memories (id, user_id, key, content, category, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET "
            "content=excluded.content, category=excluded.category, "
            "updated_at=excluded.updated_at",
            (mem_id, user_id, key, content, category, now, now),
        )
        db.commit()
    return {"id": mem_id, "user_id": user_id, "key": key,
            "content": content, "category": category, "updated_at": now}


def list_memories(user_id=DEFAULT_USER_ID):
    """Return all memories for a user, newest-updated first."""
    with _lock:
        db = _db()
        rows = db.execute(
            "SELECT id, user_id, key, content, category, "
            "created_at, updated_at FROM memories "
            "WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [
        {
            "id": r["id"], "user_id": r["user_id"], "key": r["key"],
            "content": r["content"], "category": r["category"],
            "created_at": r["created_at"], "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def delete_memory(mem_id):
    """Delete a single memory by its id. Returns True if deleted."""
    with _lock:
        db = _db()
        cur = db.execute("DELETE FROM memories WHERE id = ?", (mem_id,))
        db.commit()
        return cur.rowcount > 0
