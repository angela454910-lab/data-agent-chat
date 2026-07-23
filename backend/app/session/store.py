"""Session store: JSON file-based persistence for chat sessions."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

SESSIONS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sessions"


def _ensure_dir() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def _now_iso() -> str:
    return datetime.now().isoformat()


def _write(session_id: str, session: dict) -> None:
    _ensure_dir()
    path = _session_path(session_id)
    path.write_text(
        json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def create_session(session_id: str) -> dict:
    """Create a new empty session."""
    session = {
        "id": session_id,
        "title": "新对话",
        "messages": [],
        "status": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _write(session_id, session)
    return session


def get_session(session_id: str) -> dict | None:
    """Return a full session dict, or None if not found."""
    path = _session_path(session_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_or_create(session_id: str) -> dict:
    """Return existing session or create a new one."""
    session = get_session(session_id)
    if session is None:
        session = create_session(session_id)
    return session


def list_sessions() -> list[dict]:
    """List all sessions (without messages) sorted by updated_at desc."""
    _ensure_dir()
    summaries: list[dict] = []
    for path in SESSIONS_DIR.glob("*.json"):
        try:
            s = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        summaries.append(
            {
                "id": s["id"],
                "title": s.get("title", "新对话"),
                "status": s.get("status"),
                "updated_at": s.get("updated_at", ""),
                "created_at": s.get("created_at", ""),
                "message_count": len(s.get("messages", [])),
            }
        )
    summaries.sort(key=lambda x: x["updated_at"], reverse=True)
    return summaries


def delete_session(session_id: str) -> bool:
    """Delete a session file. Returns True if deleted."""
    path = _session_path(session_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def append_message(session_id: str, message: dict) -> dict | None:
    """Append a message to a session."""
    session = get_session(session_id)
    if session is None:
        return None
    session["messages"].append(message)
    session["updated_at"] = _now_iso()
    _write(session_id, session)
    return session


def update_session(session_id: str, updates: dict[str, Any]) -> dict | None:
    """Merge updates into a session."""
    session = get_session(session_id)
    if session is None:
        return None
    session.update(updates)
    session["updated_at"] = _now_iso()
    _write(session_id, session)
    return session


def update_metadata(session_id: str, metadata: dict[str, Any]) -> dict | None:
    """Merge metadata fields into session.metadata."""
    session = get_session(session_id)
    if session is None:
        return None
    session.setdefault("metadata", {})
    session["metadata"].update(metadata)
    session["updated_at"] = _now_iso()
    _write(session_id, session)
    return session


def derive_title(message: str) -> str:
    """Derive a session title from the first user message."""
    text = message.strip()
    return text[:20] + "..." if len(text) > 20 else text
