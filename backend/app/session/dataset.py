"""Per-session dataset store.

Holds uploaded DataFrames keyed by session_id. Uses contextvars so that
LangChain tools (which have no access to the request context) can look up
the current session's dataset without threading session_id through every
function call.
"""

from __future__ import annotations

import contextvars
import threading
from dataclasses import dataclass, field

import pandas as pd

_current_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "dataset_session_id", default=""
)

_store: dict[str, "DatasetEntry"] = {}
_lock = threading.Lock()


@dataclass
class DatasetEntry:
    name: str
    filename: str
    file_type: str
    df: pd.DataFrame
    columns: list[dict] = field(default_factory=list)
    row_count: int = 0
    created_at: str = ""

    def schema_text(self) -> str:
        lines = [f"Dataset: {self.name} (file: {self.filename})"]
        lines.append(f"Rows: {self.row_count}")
        lines.append("Columns:")
        for c in self.columns:
            samples = c.get("sample_values", "")
            lines.append(
                f"  - {c['name']} ({c['type']}): "
                f"samples=[{samples}], "
                f"unique={c.get('unique_count','?')}, "
                f"nulls={c.get('null_count','?')}"
            )
        return "\n".join(lines)


def set_session_id(sid: str) -> None:
    _current_session_id.set(sid)


def get_current_session_id() -> str:
    return _current_session_id.get()


def store_dataset(session_id, df, filename, file_type, name=None):
    columns = _infer_columns(df)
    entry = DatasetEntry(
        name=name or filename,
        filename=filename,
        file_type=file_type,
        df=df,
        columns=columns,
        row_count=len(df),
    )
    with _lock:
        _store[session_id] = entry
    return entry


def get_dataset(session_id=None):
    sid = session_id or get_current_session_id()
    if not sid:
        return None
    with _lock:
        return _store.get(sid)


def delete_dataset(session_id: str) -> bool:
    with _lock:
        return _store.pop(session_id, None) is not None


def has_dataset(session_id=None) -> bool:
    return get_dataset(session_id) is not None


def _infer_columns(df: pd.DataFrame) -> list[dict]:
    cols: list[dict] = []
    for col in df.columns:
        dtype = df[col].dtype
        if pd.api.types.is_numeric_dtype(dtype):
            ctype = "number"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            ctype = "datetime"
        elif pd.api.types.is_bool_dtype(dtype):
            ctype = "boolean"
        else:
            ctype = "string"
        non_null = df[col].dropna()
        samples = non_null.head(3).tolist()
        sample_str = ", ".join(str(s) for s in samples) if samples else "(empty)"
        cols.append({
            "name": str(col),
            "type": ctype,
            "title": str(col),
            "sample_values": sample_str,
            "null_count": int(df[col].isna().sum()),
            "unique_count": int(df[col].nunique()),
        })
    return cols


def dataset_to_dict(entry: DatasetEntry) -> dict:
    return {
        "name": entry.name,
        "filename": entry.filename,
        "file_type": entry.file_type,
        "row_count": entry.row_count,
        "columns": entry.columns,
    }
