"""Volcengine Ark (Doubao) Agent -- standalone, does not touch existing agents.

Uses the OpenAI-compatible Ark API endpoint with the doubao model.
When a dataset is uploaded for the session, the model gets dataset tools
(describe_dataset, query_dataset, aggregate_dataset) and a system prompt
that instructs it to analyze the uploaded data.  Without a dataset it
behaves as a plain chat assistant.
"""

from __future__ import annotations

import os
import json
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.session.dataset import get_dataset, set_session_id
from app.tools.dataset_tools import DATASET_TOOLS

ARK_BASE_URL = os.getenv(
    "ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
)
ARK_API_KEY = os.getenv(
    "ARK_API_KEY"
)
ARK_MODEL = os.getenv("ARK_MODEL", "doubao-seed-2-1-pro-260628")

CHAT_SYSTEM_PROMPT = (
    "You are an AI assistant powered by Volcengine Doubao. "
    "Answer questions, hold conversations, and provide suggestions. "
    "Respond in Chinese. Be friendly, concise, and organized."
)

DATASET_SYSTEM_PROMPT = """你是一个数据分析助手，由火山方舟 Doubao 模型驱动。用户上传了数据文件（Excel/JSON/CSV），你的职责是帮助用户探索和分析这份数据。

工作流程:
1. 先调用 describe_dataset 了解数据集的列名、类型和样本值
2. 根据用户问题使用 query_dataset 或 aggregate_dataset 查询数据
3. 基于查询结果给出清晰、有结论性的分析

过滤条件格式:
- 精确匹配: {"列名": "值"}
- 列表匹配: {"列名": ["值1", "值2"]}
- 范围过滤: {"列名": {"gte": 100, "lte": 500}}

分析原则:
- 先理解数据结构再查询，避免盲目猜测列名
- 获取到足够数据后立即给出结论，不要反复查询
- 对于开放式问题，基于已有数据给出具体洞察和建议
- 回答中引用具体数字，让结论可验证
- 用中文回答
"""


def _get_model(streaming: bool = True) -> ChatOpenAI:
    """Create a ChatOpenAI instance configured for the Volcengine Ark API."""
    return ChatOpenAI(
        model=ARK_MODEL,
        openai_api_key=ARK_API_KEY,
        openai_api_base=ARK_BASE_URL,
        temperature=0.1,
        streaming=streaming,
        max_retries=2,
    )


def _build_history(history: list[dict]) -> list[BaseMessage]:
    """Convert persisted history dicts into LangChain messages."""
    messages: list[BaseMessage] = []
    for m in history:
        role = m.get("role", "")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "agent":
            messages.append(AIMessage(content=content))
    return messages


def _run_tool(tool_func, tool_input: dict) -> str:
    """Call a LangChain tool and return its string output."""
    try:
        result = tool_func.invoke(tool_input)
        return str(result)
    except Exception as e:
        return f"Tool error: {e}"


async def stream_volcengine_chat(
    message: str,
    history: list[dict] | None = None,
    session_id: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Stream a chat response from the Volcengine Doubao model.

    When a dataset is uploaded for the session, the model gets dataset
    tools and a data-analysis system prompt.  Without a dataset it's a
    plain chat.  Yields SSE-compatible dict events.
    """
    if not message or not message.strip():
        yield {"type": "answer", "content": "Please enter a question."}
        return

    set_session_id(session_id or "")
    has_dataset = session_id and get_dataset(session_id) is not None

    if has_dataset:
        async for event in _stream_with_tools(message, history or [], session_id):
            yield event
    else:
        async for event in _stream_chat(message, history or []):
            yield event


async def _stream_chat(message: str, history: list[dict]) -> AsyncGenerator[dict, None]:
    """Plain chat without dataset tools."""
    model = _get_model()
    messages = _build_history(history)
    messages.insert(0, HumanMessage(content=CHAT_SYSTEM_PROMPT))
    messages.append(HumanMessage(content=message))

    extra_body = {}
    if os.getenv("ARK_DISABLE_THINKING", "1") == "1":
        extra_body["thinking"] = {"type": "disabled"}

    try:
        async for chunk in model.astream(messages, extra_body=extra_body):
            if chunk.content:
                yield {"type": "answer", "content": chunk.content}
    except Exception as e:
        yield {"type": "error", "content": str(e)}


async def _stream_with_tools(
    message: str, history: list[dict], session_id: str
) -> AsyncGenerator[dict, None]:
    """Chat with dataset tools when a dataset is uploaded.

    Uses the model's native function-calling: sends the tool definitions,
    and if the model requests a tool call, executes it locally and feeds
    the result back in a second LLM round.
    """
    model = _get_model().bind_tools(DATASET_TOOLS)
    messages = _build_history(history)
    messages.insert(0, HumanMessage(content=DATASET_SYSTEM_PROMPT))
    messages.append(HumanMessage(content=message))

    extra_body = {}
    if os.getenv("ARK_DISABLE_THINKING", "1") == "1":
        extra_body["thinking"] = {"type": "disabled"}

    try:
        MAX_ROUNDS = 5  # safety limit to prevent infinite tool-call loops
        for _round in range(MAX_ROUNDS):
            # Invoke the model (non-streaming) to check for tool calls
            response = await model.ainvoke(messages, extra_body=extra_body)
            tool_calls = getattr(response, "tool_calls", None) or []

            if not tool_calls:
                # No more tool calls -- stream the final answer
                content = response.content
                if content:
                    yield {"type": "answer", "content": content}
                return

            # Execute all requested tool calls in this round
            messages.append(response)
            for tc in tool_calls:
                tool_name = tc["name"]
                tool_input = tc.get("args", {})
                tool_call_id = tc.get("id", "")
                yield {
                    "type": "tool_call",
                    "tool": tool_name,
                    "input": json.dumps(tool_input, ensure_ascii=False),
                }

                tool_func = next(
                    (t for t in DATASET_TOOLS if t.name == tool_name), None
                )
                if tool_func:
                    output = _run_tool(tool_func, tool_input)
                else:
                    output = f"Unknown tool: {tool_name}"

                if len(output) > 3000:
                    output = output[:3000] + "..."
                yield {"type": "tool_result", "tool": tool_name, "output": output}

                messages.append(ToolMessage(
                    content=output,
                    tool_call_id=tool_call_id,
                ))

        # If we hit MAX_ROUNDS, do a final streaming call for an answer
        async for chunk in model.astream(messages, extra_body=extra_body):
            if chunk.content:
                yield {"type": "answer", "content": chunk.content}

    except Exception as e:
        yield {"type": "error", "content": str(e)}
