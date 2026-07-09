"""FastAPI application: HTTP entry point for the data agent."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agents.supervisor import invoke_supervisor, stream_supervisor
from app.schema.catalog import get_schema_summary

BACKEND_DIR = Path(__file__).resolve().parent.parent
WEB_DIST_DIR = BACKEND_DIR.parent / "web" / "dist"


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


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    routed_to: str
    question: str


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


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message or not request.message.strip():
        return {"answer": "请输入问题", "routed_to": "none", "question": ""}
    result = await invoke_supervisor(request.message.strip())
    return {
        "answer": result["answer"],
        "routed_to": result["routed_to"],
        "question": request.message,
    }


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in stream_supervisor(request.message.strip()):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3009)
