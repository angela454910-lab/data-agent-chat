"""Supervisor Agent: simple YOLO analysis only."""

from __future__ import annotations

import json
import asyncio
import time
from typing import AsyncGenerator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.agents.yolo_analysis_agent import yolo_analysis_agent
from app.llm import get_chat_model
from app.session.store import list_memories, DEFAULT_USER_ID


# Prevent agents from looping indefinitely on open-ended questions
AGENT_CONFIG = {"recursion_limit": 50}


def _extract_answer(messages: list) -> str:
    """Extract the last AI message content from a message list."""
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            return m.content
    return ""


def _handle_recursion_error(e: Exception) -> str:
    """Check if error is a recursion limit error and return a user-friendly message."""
    error_str = str(e).lower()
    if "recursion limit" in error_str or "recursion_limit" in error_str:
        return "分析过程过于复杂，请尝试将问题拆分成更具体的小问题。"
    return f"处理出错: {str(e)}"


def _extract_tool_output(raw_output) -> str:
    """Extract readable string from tool output (ToolMessage, dict, or string)."""
    # LangChain ToolMessage / BaseMessage with .content
    if hasattr(raw_output, "content") and raw_output.content:
        return str(raw_output.content)
    if isinstance(raw_output, str):
        return raw_output
    if isinstance(raw_output, dict):
        return json.dumps(raw_output, ensure_ascii=False, indent=2)
    return str(raw_output)


def _build_memory_block(user_id: str = DEFAULT_USER_ID) -> str:
    """Return a long-term-memory prefix for the user, or '' if none stored."""
    try:
        memories = list_memories(user_id)
    except Exception:
        return ""
    if not memories:
        return ""
    lines = "\n".join(f"- {m['content']}" for m in memories)
    return (
        "以下是关于该用户的长期记忆（偏好、口径纠正、背景），"
        "回答时请优先遵守：\n" + lines
    )


def _with_memory(text: str, block: str | None = None) -> str:
    """Prepend the user's memory block to a message, if any memories exist."""
    if block is None:
        block = _build_memory_block()
    if not block:
        return text
    return f"{block}\n\n{text}"


def _compose_question(question: str, memory_block: str = "") -> str:
    """Stack context blocks (memory) above the question text."""
    return "\n\n".join(p for p in (memory_block, question) if p)


def build_history(
    turns: list[dict] | None,
    max_turns: int = 6,
    max_answer_chars: int = 1500,
) -> list[BaseMessage]:
    """Convert persisted session messages into LC history."""
    if not turns:
        return []

    qa = [
        m for m in turns
        if m.get("role") in ("user", "agent") and (m.get("content") or "").strip()
    ]
    windowed = qa[-max_turns * 2:]
    # History must start with a user turn so roles alternate cleanly.
    while windowed and windowed[0]["role"] != "user":
        windowed.pop(0)

    messages: list[BaseMessage] = []
    for m in windowed:
        if m["role"] == "user":
            messages.append(HumanMessage(content=m["content"]))
        else:
            messages.append(AIMessage(content=m["content"][:max_answer_chars]))

    return messages


async def stream_supervisor(message: str, history: list[dict] | None = None) -> AsyncGenerator[dict, None]:
    """Stream supervisor events including tool calls and results for YOLO analysis only.

    `history` is the session's persisted messages, excluding the current user message.
    """
    if not message or not message.strip():
        yield {"type": "answer", "content": "请输入问题"}
        return

    history_msgs = build_history(history)
    memory_block = _build_memory_block()

    initial_state = {
        "messages": [*history_msgs, HumanMessage(content=_compose_question(message, memory_block))],
        "next_agent": "yolo_analysis",
    }

    try:
        answer = ""
        async for event in yolo_analysis_agent.astream_events(initial_state, version="v2", config=AGENT_CONFIG):
            kind = event.get("event", "")

            if kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                answer = ""  # discard pre-tool model chatter; keep only the final answer
                yield {
                    "type": "tool_call",
                    "tool": tool_name,
                    "input": json.dumps(tool_input, ensure_ascii=False, indent=2) if isinstance(tool_input, dict) else str(tool_input)
                }

            elif kind == "on_tool_end":
                tool_name = event.get("name", "unknown")
                tool_output = event.get("data", {}).get("output", "")
                output_str = _extract_tool_output(tool_output)
                if len(output_str) > 2000:
                    output_str = output_str[:2000] + "..."
                yield {
                    "type": "tool_result",
                    "tool": tool_name,
                    "output": output_str
                }

            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    answer += chunk.content

        # The final answer is whatever the model streamed after the last tool call
        yield {"type": "answer", "content": answer or "无法回答"}

    except Exception as e:
        yield {"type": "error", "content": _handle_recursion_error(e)}
