"""Memory extraction: pull durable user facts from a finished turn.

Runs as a background LLM call after the agent answer is persisted. Failures
are logged and swallowed -- extraction must never break the chat flow.
"""

from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.messages import HumanMessage

from app.llm import get_chat_model
from app.session.store import upsert_memory, list_memories, DEFAULT_USER_ID


# Skip the (non-)LLM call when the project is in mock/offline mode.
_USE_MOCK = os.getenv("USE_MOCK", "false").lower() in ("1", "true", "yes")


EXTRACTION_PROMPT = """你是一个信息提取器。从下面这一轮对话中提取值得长期记住的用户信息。

只提取以下几类：
- preference: 用户明确表达的分析偏好（默认时间范围、关注指标、偏好维度、输出形式如"先给结论"/"带SQL"）
- correction: 用户对指标口径或业务规则的纠正（如"退款率分母用支付订单数"）
- context: 用户的角色背景（部门、负责的业务线、常用数据范围）

规则：
- 只记用户**明确表达**的信息，不要从查询内容或结果里猜测
- 如果新信息是对已有记忆的更新，复用已有 key（用 snake_case）
- 没有可记的就返回空数组

已有记忆 keys: {existing_keys}

用户说：{user_message}
Agent 回答：{agent_answer}

只输出 JSON 数组，不要输出其他内容：
[{{"key": "snake_case_标识", "content": "记忆内容", "category": "preference|correction|context"}}]"""


def _parse_memories(raw: str) -> list[dict[str, Any]]:
    """Best-effort parse of the JSON array returned by the LLM."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        items = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    out: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        key = (it.get("key") or "").strip()
        content = (it.get("content") or "").strip()
        if not key or not content:
            continue
        category = (it.get("category") or "preference").strip()
        if category not in ("preference", "correction", "context"):
            category = "preference"
        out.append({"key": key, "content": content, "category": category})
    return out


def extract_and_store_memories(
    user_message: str,
    agent_answer: str,
    user_id: str = DEFAULT_USER_ID,
) -> int:
    """Extract durable facts from a turn and persist them. Returns count stored.

    Safe to call as a fire-and-forget asyncio task: any error is logged and
    swallowed.
    """
    if _USE_MOCK:
        return 0
    if not (user_message and user_message.strip()):
        return 0
    if not agent_answer or not agent_answer.strip():
        return 0

    try:
        existing = [m["key"] for m in list_memories(user_id)]
        prompt = EXTRACTION_PROMPT.format(
            existing_keys=", ".join(existing) or "(无)",
            user_message=user_message,
            agent_answer=agent_answer[:2000],
        )
        model = get_chat_model(temperature=0.0)
        response = model.invoke([HumanMessage(content=prompt)])
        items = _parse_memories(response.content)
        stored = 0
        for it in items:
            upsert_memory(user_id, it["key"], it["content"], it["category"])
            stored += 1
        if stored:
            print(f"[Memory] stored {stored} memories from this turn")
        return stored
    except Exception as e:
        print(f"[Memory] extraction failed (non-fatal): {e}")
        return 0
