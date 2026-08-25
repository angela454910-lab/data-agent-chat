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


# Single routing prompt for both first-turn and follow-up questions: resolves
# references ("这个结论", "那上个月呢") into a standalone question AND
# classifies, in one LLM call. With no history, the rewrite rule is a no-op
# and the question passes through unchanged.
ROUTING_PROMPT = """你是一个意图分类器。根据对话历史和用户最新问题，完成两件事：
1. 如果最新问题依赖上文（如"这个"、"那"、"上述结论"等指代，或省略了指标/时间范围等关键信息），将其改写为包含必要上下文的独立问题；如果问题本身完整独立，原样保留
2. 判断改写后的问题应该由哪个 Agent 处理，或是否应该拒绝回答

可选 Agent：
- business_knowledge: 业务概念、指标定义、政策规则、口径说明、计算方式等知识类问题，也包含问候语（如"你好"）、感谢、系统能力询问（如"你能做什么"）等对话类问题
- data_analysis: 数据查询、统计分析、趋势对比、排名、具体数值等数据类问题；基于此前结论的追问（如"针对这个结论怎么做"）也算数据类
- both: 同时涉及知识问答和数据分析的混合问题（例如"退款率怎么算？最近30天是多少？"）
- out_of_scope: 与数据分析或业务指标完全无关的问题，或需要外部常识/网络搜索才能回答的问题（例如天气、写诗、讲笑话、AI术语解释、历史事件、体育赛事、明星八卦等）。注意：问候语、感谢、系统能力询问不属于 out_of_scope

对话历史：
{history}

用户最新问题：{question}

只输出 JSON，不要输出其他内容：
{{"question": "改写后的独立问题", "agent": "business_knowledge" | "data_analysis" | "both" | "out_of_scope", "confidence": 0.0-1.0, "reason": "简要理由"}}"""

# 拒绝消息模板 — 当意图分类为 out_of_scope 时返回
# TODO: 后续可考虑使用本地算法（如 embedding 相似度、关键词预过滤）在 LLM 分类前快速拦截明显无关问题，进一步减少 token 消耗
OUT_OF_SCOPE_MESSAGE = "请提出与数据分析或业务指标相关的问题，比如「最近30天销售额是多少？」或「退款率怎么计算？」"

# Prevent agents from looping indefinitely on open-ended questions
AGENT_CONFIG = {"recursion_limit": 50}


def _format_history_text(turns: list[dict], max_turns: int = 3, max_answer_chars: int = 500) -> str:
    """Render recent persisted turns as plain text for the routing prompt."""
    qa = [
        m for m in turns
        if m.get("role") in ("user", "agent") and (m.get("content") or "").strip()
    ]
    lines = []
    for m in qa[-max_turns * 2:]:
        role = "用户" if m["role"] == "user" else "助手"
        lines.append(f"{role}: {m['content'][:max_answer_chars]}")
    return "\n".join(lines)


def classify_intent(question: str, history_text: str = "") -> tuple[str, str]:
    """Classify intent and determine routing.

    Returns (agent_name, standalone_question). With history present, the same
    LLM call also rewrites follow-up references into a self-contained
    question; without history the question passes through unchanged.
    """
    model = get_chat_model(temperature=0.0)
    prompt = ROUTING_PROMPT.format(history=history_text or "（无）", question=question)

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
        standalone = (result.get("question") or "").strip() or question
        if standalone != question:
            print(f"[Supervisor] Follow-up rewritten: {question!r} -> {standalone!r}")
        return agent, standalone
    except (json.JSONDecodeError, KeyError, Exception) as e:
        print(f"[Supervisor] Intent classification failed: {e}, falling back to data_analysis")
        return "data_analysis", question


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


def _compose_question(question: str, memory_block: str = "", evidence_block: str = "") -> str:
    """Stack context blocks (memory, data evidence) above the question text."""
    return "\n\n".join(p for p in (memory_block, evidence_block, question) if p)


def build_history(
    turns: list[dict] | None,
    max_turns: int = 6,
    max_answer_chars: int = 1500,
    max_evidence_items: int = 4,
    max_evidence_chars: int = 1000,
) -> tuple[list[BaseMessage], str]:
    """Convert persisted session messages into LC history + an evidence block.

    Window policy: the most recent agent turn also contributes its tool
    results as a plain-text "evidence" block for the follow-up question;
    older turns are question/answer pairs only (answers truncated).

    Evidence stays out of the message list on purpose: a LangChain
    ToolMessage must answer a matching tool_call, so injecting raw
    ToolMessages would require reconstructing the previous turn's whole
    tool-call chain. A labeled text block carries the same information
    without the protocol coupling.
    """
    if not turns:
        return [], ""

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

    evidence = ""
    last_agent = next((m for m in reversed(qa) if m["role"] == "agent"), None)
    if last_agent:
        results = [
            s for s in (last_agent.get("steps") or [])
            if s.get("type") == "tool_result" and s.get("detail")
        ][-max_evidence_items:]
        if results:
            lines = [str(r["detail"])[:max_evidence_chars] for r in results]
            evidence = (
                "【此前查询到的数据】（上一轮分析的工具返回，供参考；"
                "如需最新或不同维度的数据请重新查询）\n" + "\n".join(lines)
            )
    return messages, evidence


async def invoke_supervisor(message: str, history: list[dict] | None = None) -> dict:
    """Invoke the supervisor with a user message (non-streaming)."""
    if not message or not message.strip():
        return {"answer": "请输入问题"}

    history_text = _format_history_text(history or [])
    agent_name, question = classify_intent(message, history_text)

    if agent_name == "out_of_scope":
        return {"answer": OUT_OF_SCOPE_MESSAGE}

    history_msgs, evidence = build_history(history)
    # Memory is relevant only for data analysis; skip for knowledge/greetings.
    # Same for the data-evidence block.
    if agent_name in ("data_analysis", "both"):
        memory_block = _build_memory_block()
    else:
        memory_block, evidence = "", ""


    try:
        if agent_name == "both":
            biz_state = {
                "messages": [*history_msgs, HumanMessage(content=_compose_question(question, memory_block))],
                "next_agent": "business_knowledge",
            }
            biz_result = _retry_sync(business_knowledge_agent.invoke, biz_state, config=AGENT_CONFIG)
            biz_answer = _extract_answer(biz_result.get("messages", []))

            context_prefix = f"以下是相关的业务知识背景，请在分析时参考：\n{biz_answer}\n\n用户问题：{question}"
            data_state = {
                "messages": [*history_msgs, HumanMessage(content=_compose_question(context_prefix, memory_block, evidence))],
                "next_agent": "data_analysis",
            }
            data_result = _retry_sync(data_analysis_agent.invoke, data_state, config=AGENT_CONFIG)
            answer = _extract_answer(data_result.get("messages", []))
            return {"answer": answer or "无法回答这个问题"}

        initial_state = {
            "messages": [*history_msgs, HumanMessage(content=_compose_question(question, memory_block, evidence))],
            "next_agent": agent_name,
        }

        if agent_name == "data_analysis":
            agent = data_analysis_agent
        else:
            agent = business_knowledge_agent
        result = _retry_sync(agent.invoke, initial_state, config=AGENT_CONFIG)
        answer = _extract_answer(result.get("messages", []))
        return {"answer": answer or "无法回答这个问题"}

    except Exception as e:
        return {"answer": _handle_recursion_error(e)}


async def stream_supervisor(message: str, history: list[dict] | None = None) -> AsyncGenerator[dict, None]:
    """Stream supervisor events including tool calls and results.

    `history` is the session's persisted messages (as stored by
    session/store.py), excluding the current user message.
    """
    if not message or not message.strip():
        yield {"type": "answer", "content": "请输入问题"}
        return

    history_text = _format_history_text(history or [])

    # classify_intent runs a synchronous LLM call (model.invoke + blocking
    # time.sleep retries). Off-load it to a worker thread so it doesn't hold
    # the event loop -- otherwise concurrent requests (e.g. the sidebar
    # fetching the session the user just switched to) stall behind it.
    agent_name, question = await asyncio.to_thread(classify_intent, message, history_text)

    if agent_name == "out_of_scope":
        yield {"type": "answer", "content": OUT_OF_SCOPE_MESSAGE}
        return

    history_msgs, evidence = build_history(history)
    # Memory is relevant only for data analysis; skip for knowledge/greetings.
    # Same for the data-evidence block.
    if agent_name in ("data_analysis", "both"):
        memory_block = _build_memory_block()
    else:
        memory_block, evidence = "", ""


    if agent_name == "both":
        biz_state = {
            "messages": [*history_msgs, HumanMessage(content=_compose_question(question, memory_block))],
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

        context_prefix = f"以下是相关的业务知识背景，请在分析时参考：\n{biz_answer}\n\n用户问题：{question}"
        data_state = {
            "messages": [*history_msgs, HumanMessage(content=_compose_question(context_prefix, memory_block, evidence))],
            "next_agent": "data_analysis",
        }

        try:
            answer = ""
            async for event in _retry_async(data_analysis_agent.astream_events, data_state, version="v2", config=AGENT_CONFIG):
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

            # The final answer is whatever the model streamed after the last
            # tool call; the invoke re-run is no longer needed.
            print(f"[Supervisor] answer collected from on_chat_model_stream events ({len(answer)} chars), invoke re-run skipped", flush=True)
            yield {"type": "answer", "content": answer or "无法回答"}

        except Exception as e:
            yield {"type": "error", "content": _handle_recursion_error(e)}
        return

    initial_state = {
            "messages": [*history_msgs, HumanMessage(content=_compose_question(question, memory_block, evidence))],
            "next_agent": agent_name,
        }
    if agent_name == "data_analysis":
        agent = data_analysis_agent
    else:
        agent = business_knowledge_agent

    try:
        answer = ""
        async for event in _retry_async(agent.astream_events, initial_state, version="v2", config=AGENT_CONFIG):
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

        # The final answer is whatever the model streamed after the last tool
        # call; the invoke re-run is no longer needed.
        yield {"type": "answer", "content": answer or "无法回答"}

    except Exception as e:
        yield {"type": "error", "content": _handle_recursion_error(e)}
