"""FastAPI application: HTTP entry point for the data agent."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agents.supervisor import stream_supervisor
from app.agents.summary import generate_summary
from app.schema.catalog import get_schema_summary
from app.session.store import (
    get_or_create,
    get_session,
    list_sessions,
    delete_session,
    append_message,
    update_session,
    update_metadata,
    derive_title,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent
WEB_DIST_DIR = BACKEND_DIR.parent / "web" / "dist"

# Debounce timers for summary generation: session_id -> asyncio.Task
_summary_tasks: dict[str, asyncio.Task] = {}
_SUMMARY_DEBOUNCE_SECONDS = 30


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Data Agent starting...")
    print(f"Backend dir: {BACKEND_DIR}")
    print(f"Web dist dir: {WEB_DIST_DIR}")
    print(f"Web dist exists: {WEB_DIST_DIR.exists()}")
    yield
    print("Data Agent shutting down...")


app = FastAPI(title="Data Agent Chat", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve built frontend if available
if WEB_DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST_DIR / "assets"), name="assets")



class ChatStreamRequest(BaseModel):
    message: str
    session_id: str | None = None


class SummaryRequest(BaseModel):
    messages: list[dict]



@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the frontend: built React app or fallback to test.html."""
    index_path = WEB_DIST_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    fallback = BACKEND_DIR / "test.html"
    if fallback.exists():
        return HTMLResponse(fallback.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Data Agent Chat</h1><p>Frontend not built. Run <code>cd web && npm run build</code></p>")


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "data-agent-chat", "version": "0.2.0"}


@app.get("/api/schema")
async def schema():
    return {"tables": get_schema_summary()}


def _extract_tables(tool_name: str, tool_input_str: str) -> list[str]:
    """Extract table names from a tool call's input."""
    try:
        ti = json.loads(tool_input_str) if isinstance(tool_input_str, str) else tool_input_str
    except (json.JSONDecodeError, TypeError):
        return []
    tables: list[str] = []
    if tool_name in ("query_data", "aggregate_data", "describe_table"):
        t = ti.get("table_name")
        if t:
            tables.append(t)
    elif tool_name == "join_and_query":
        for key in ("left_table", "right_table"):
            t = ti.get(key)
            if t:
                tables.append(t)
    return tables


@app.get("/api/sessions")
async def sessions_list():
    return {"sessions": list_sessions()}


@app.get("/api/sessions/{session_id}")
async def session_detail(session_id: str):
    session = get_session(session_id)
    if session is None:
        return {"error": "session not found"}, 404
    return session


@app.delete("/api/sessions/{session_id}")
async def session_delete(session_id: str):
    deleted = delete_session(session_id)
    return {"deleted": deleted}


@app.post("/api/chat/summary")
async def chat_summary(request: SummaryRequest):
    """Generate a session summary from conversation messages."""
    summary = generate_summary(request.messages)
    return {"summary": summary}


def _schedule_summary(session_id: str) -> None:
    """Schedule a debounced summary generation for a session."""
    # Cancel any existing pending task
    existing = _summary_tasks.get(session_id)
    if existing and not existing.done():
        existing.cancel()

    async def _generate():
        try:
            await asyncio.sleep(_SUMMARY_DEBOUNCE_SECONDS)
            session = get_session(session_id)
            if session is None:
                return
            messages = session.get("messages", [])
            if len(messages) < 2:
                return
            summary = generate_summary(messages)
            if summary:
                update_metadata(session_id, {"summary": summary})
                print(f"[Summary] Generated for session {session_id}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[Summary] Error for session {session_id}: {e}")
        finally:
            _summary_tasks.pop(session_id, None)

    _summary_tasks[session_id] = asyncio.ensure_future(_generate())


@app.post("/api/chat/stream")
async def chat_stream(request: ChatStreamRequest):
    session_id = request.session_id
    message = request.message.strip()

    if session_id:
        get_or_create(session_id)
        append_message(session_id, {
            "id": f"msg-{int(time.time())}-u",
            "role": "user",
            "content": message,
            "timestamp": int(time.time()),
            "steps": [],
        })
        update_session(session_id, {"status": "thinking"})

    async def event_generator() -> AsyncGenerator[str, None]:
        accumulated_answer = ""
        accumulated_steps: list[dict] = []
        tables_used: set[str] = set()
        step_counter = 0

        try:
            async for event in stream_supervisor(message):
                if event.get("type") in ("answer", "sub_answer"):
                    accumulated_answer += event.get("content", "")
                elif event.get("type") == "tool_call":
                    step_counter += 1
                    accumulated_steps.append({
                        "id": f"step-{step_counter}",
                        "type": "tool_call",
                        "label": f"调用工具: {event.get('tool')}",
                        "detail": event.get("input"),
                        "timestamp": int(time.time()),
                    })
                    tables_used.update(_extract_tables(event.get("tool", ""), event.get("input", "")))
                elif event.get("type") == "tool_result":
                    step_counter += 1
                    accumulated_steps.append({
                        "id": f"step-{step_counter}",
                        "type": "tool_result",
                        "label": f"{event.get('tool')} 返回结果",
                        "detail": event.get("output"),
                        "timestamp": int(time.time()),
                    })

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            if session_id:
                append_message(session_id, {
                    "id": f"msg-{int(time.time())}-a",
                    "role": "agent",
                    "content": accumulated_answer,
                    "timestamp": int(time.time()),
                    "steps": accumulated_steps,
                })
                update_metadata(session_id, {"tables": list(tables_used)})
                current = get_session(session_id) or {}
                updates: dict = {"status": "done"}
                if current.get("title") == "新对话":
                    updates["title"] = derive_title(message)
                update_session(session_id, updates)
                # Schedule debounced summary generation
                _schedule_summary(session_id)

            yield "data: [DONE]\n\n"
        except Exception as e:
            if session_id:
                update_session(session_id, {"status": "error"})
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3009)
