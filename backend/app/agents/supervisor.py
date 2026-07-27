"""Supervisor Agent: orchestrates multiple agents with streaming events."""

from __future__ import annotations

import json
import asyncio
import time
from typing import TypedDict, AsyncGenerator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.agents.business_knowledge import business_knowledge_agent
from app.agents.data_analysis import data_analysis_agent
from app.llm import get_chat_model
from app.session.store import list_memories, DEFAULT_USER_ID


class AgentState(TypedDict):
    """State for the supervisor graph."""
    messages: list[BaseMessage]
    next_agent: str


# Retry configuration for LLM calls (supplements OpenAI SDK's built-in retry)
_RETRY_MAX_ATTEMPTS = 3
_RETRY_INITIAL_BACKOFF = 2.0  # seconds
_RETRY_BACKOFF_MULTIPLIER = 2.0
_RETRY_MAX_BACKOFF = 30.0  # seconds


def _is_retryable(error: Exception) -> bool:
    """Check if an error is transient (rate limit / server error)."""
    msg = str(error).lower()
    return any(kw in msg for kw in ("429", "rate limit", "rate exceeded", "rate increased", "too many requests"))


def _retry_sync(fn, *args, **kwargs):
    """Execute fn with exponential backoff retry for transient errors."""
    last_error = None
    for attempt in range(_RETRY_MAX_ATTEMPTS + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_error = e
            if not _is_retryable(e) or attempt >= _RETRY_MAX_ATTEMPTS:
                raise
            backoff = min(_RETRY_INITIAL_BACKOFF * (_RETRY_BACKOFF_MULTIPLIER ** attempt), _RETRY_MAX_BACKOFF)
            print(f"[Supervisor] Retryable error (attempt {attempt + 1}/{_RETRY_MAX_ATTEMPTS}), "
                  f"backing off {backoff:.1f}s: {e}")
            time.sleep(backoff)
    raise last_error  # type: ignore[misc]


async def _retry_async(agen_fn, *args, **kwargs):
    """Execute an async generator with retry on the initial connection.

    Retries only at entry point — once streaming begins, it runs uninterrupted.
    """
    import asyncio
    last_error = None
    for attempt in range(_RETRY_MAX_ATTEMPTS + 1):
        try:
            # Create a fresh async generator for each attempt
            async for item in agen_fn(*args, **kwargs):
                yield item
            return  # success
        except Exception as e:
            last_error = e
            if not _is_retryable(e) or attempt >= _RETRY_MAX_ATTEMPTS:
                raise
            backoff = min(_RETRY_INITIAL_BACKOFF * (_RETRY_BACKOFF_MULTIPLIER ** attempt), _RETRY_MAX_BACKOFF)
            print(f"[Supervisor] Retryable error (attempt {attempt + 1}/{_RETRY_MAX_ATTEMPTS}), "
                  f"backing off {backoff:.1f}s: {e}")
            await asyncio.sleep(backoff)
    raise last_error  # type: ignore[misc]


ROUTING_PROMPT = """你是一个意图分类器。根据用户问题，判断应该由哪个 Agent 处理，或是否应该拒绝回答。

可选 Agent：
- business_knowledge: 业务概念、指标定义、政策规则、口径说明、计算方式等知识类问题，也包含问候语（如"你好"）、感谢、系统能力询问（如"你能做什么"）等对话类问题
- data_analysis: 数据查询、统计分析、趋势对比、排名、具体数值等数据类问题
- both: 同时涉及知识问答和数据分析的混合问题（例如"退款率怎么算？最近30天是多少？"）
- out_of_scope: 与数据分析或业务指标完全无关的问题，或需要外部常识/网络搜索才能回答的问题（例如天气、写诗、讲笑话、AI术语解释、历史事件、体育赛事、明星八卦等）。注意：问候语、感谢、系统能力询问不属于 out_of_scope

用户问题：{question}

只输出 JSON，不要输出其他内容：
{{"agent": "business_knowledge" | "data_analysis" | "both" | "out_of_scope", "confidence": 0.0-1.0, "reason": "简要理由"}}"""

# 拒绝消息模板 — 当意图分类为 out_of_scope 时返回
# TODO: 后续可考虑使用本地算法（如 embedding 相似度、关键词预过滤）在 LLM 分类前快速拦截明显无关问题，进一步减少 token 消耗
OUT_OF_SCOPE_MESSAGE = "请提出与数据分析或业务指标相关的问题，比如「最近30天销售额是多少？」或「退款率怎么计算？」"

# Prevent agents from looping indefinitely on open-ended questions
AGENT_CONFIG = {"recursion_limit": 50}


def classify_intent(question: str) -> str:
    """Use LLM to classify user intent and determine routing."""
    model = get_chat_model(temperature=0.0)
    prompt = ROUTING_PROMPT.format(question=question)

    try:
        response = _retry_sync(model.invoke, [HumanMessage(content=prompt)])
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            content = content.rsplit("```", 1)[0].strip()
        result = json.loads(content)
        agent = result.get("agent", "data_analysis")
        if agent not in ("business_knowledge", "data_analysis", "both", "out_of_scope"):
            agent = "data_analysis"
        return agent
    except (json.JSONDecodeError, KeyError, Exception) as e:
        print(f"[Supervisor] Intent classification failed: {e}, falling back to data_analysis")
        return "data_analysis"


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


async def invoke_supervisor(message: str) -> dict:
    """Invoke the supervisor with a user message (non-streaming)."""
    if not message or not message.strip():
        return {"answer": "请输入问题"}

    agent_name = classify_intent(message)

    if agent_name == "out_of_scope":
        return {"answer": OUT_OF_SCOPE_MESSAGE}

    # Memory is relevant only for data analysis; skip for knowledge/greetings.
    memory_block = _build_memory_block() if agent_name in ("data_analysis", "both") else ""

    try:
        if agent_name == "both":
            biz_state = {
                "messages": [HumanMessage(content=_with_memory(message, memory_block))],
                "next_agent": "business_knowledge",
            }
            biz_result = _retry_sync(business_knowledge_agent.invoke, biz_state, config=AGENT_CONFIG)
            biz_answer = _extract_answer(biz_result.get("messages", []))

            context_prefix = f"以下是相关的业务知识背景，请在分析时参考：\n{biz_answer}\n\n用户问题：{message}"
            data_state = {
                "messages": [HumanMessage(content=_with_memory(context_prefix, memory_block))],
                "next_agent": "data_analysis",
            }
            data_result = _retry_sync(data_analysis_agent.invoke, data_state, config=AGENT_CONFIG)
            answer = _extract_answer(data_result.get("messages", []))
            return {"answer": answer or "无法回答这个问题"}

        initial_state = {
            "messages": [HumanMessage(content=_with_memory(message, memory_block))],
            "next_agent": agent_name,
        }

        agent = data_analysis_agent if agent_name == "data_analysis" else business_knowledge_agent
        result = _retry_sync(agent.invoke, initial_state, config=AGENT_CONFIG)
        answer = _extract_answer(result.get("messages", []))
        return {"answer": answer or "无法回答这个问题"}

    except Exception as e:
        return {"answer": _handle_recursion_error(e)}


async def stream_supervisor(message: str) -> AsyncGenerator[dict, None]:
    """Stream supervisor events including tool calls and results."""
    if not message or not message.strip():
        yield {"type": "answer", "content": "请输入问题"}
        return

    # classify_intent runs a synchronous LLM call (model.invoke + blocking
    # time.sleep retries). Off-load it to a worker thread so it doesn't hold
    # the event loop -- otherwise concurrent requests (e.g. the sidebar
    # fetching the session the user just switched to) stall behind it.
    agent_name = await asyncio.to_thread(classify_intent, message)

    if agent_name == "out_of_scope":
        yield {"type": "answer", "content": OUT_OF_SCOPE_MESSAGE}
        return

    # Memory is relevant only for data analysis; skip for knowledge/greetings.
    memory_block = _build_memory_block() if agent_name in ("data_analysis", "both") else ""

    if agent_name == "both":
        biz_state = {
            "messages": [HumanMessage(content=_with_memory(message, memory_block))],
            "next_agent": "business_knowledge",
        }
        biz_answer = ""
        try:
            async for event in _retry_async(business_knowledge_agent.astream_events, biz_state, version="v2", config=AGENT_CONFIG):
                kind = event.get("event", "")
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield {"type": "sub_answer", "content": chunk.content}
                        biz_answer += chunk.content
        except Exception as e:
            yield {"type": "error", "content": _handle_recursion_error(e)}
            return

        context_prefix = f"以下是相关的业务知识背景，请在分析时参考：\n{biz_answer}\n\n用户问题：{message}"
        data_state = {
            "messages": [HumanMessage(content=_with_memory(context_prefix, memory_block))],
            "next_agent": "data_analysis",
        }

        try:
            async for event in _retry_async(data_analysis_agent.astream_events, data_state, version="v2", config=AGENT_CONFIG):
                kind = event.get("event", "")
                if kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
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

            # Sync invoke that re-runs the agent to extract the final answer;
            # off-loaded so it doesn't block the event loop mid-request.
            data_result = await asyncio.to_thread(
                data_analysis_agent.invoke, data_state, config=AGENT_CONFIG
            )
            answer = _extract_answer(data_result.get("messages", []))
            yield {"type": "answer", "content": answer or "无法回答"}

        except Exception as e:
            yield {"type": "error", "content": _handle_recursion_error(e)}
        return

    initial_state = {
        "messages": [HumanMessage(content=_with_memory(message, memory_block))],
        "next_agent": agent_name,
    }
    agent = data_analysis_agent if agent_name == "data_analysis" else business_knowledge_agent

    try:
        async for event in _retry_async(agent.astream_events, initial_state, version="v2", config=AGENT_CONFIG):
            kind = event.get("event", "")

            if kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
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

        # Sync invoke that re-runs the agent to extract the final answer;
        # off-loaded so it doesn't block the event loop mid-request.
        result = await asyncio.to_thread(agent.invoke, initial_state, config=AGENT_CONFIG)
        answer = _extract_answer(result.get("messages", []))
        yield {"type": "answer", "content": answer or "无法回答"}

    except Exception as e:
        yield {"type": "error", "content": _handle_recursion_error(e)}
