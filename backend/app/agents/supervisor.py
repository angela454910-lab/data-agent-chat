"""Supervisor Agent: orchestrates multiple agents with streaming events."""

from __future__ import annotations

import json
from typing import TypedDict, AsyncGenerator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.agents.business_knowledge import business_knowledge_agent
from app.agents.data_analysis import data_analysis_agent
from app.llm import get_chat_model


class AgentState(TypedDict):
    """State for the supervisor graph."""
    messages: list[BaseMessage]
    next_agent: str


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
        response = model.invoke([HumanMessage(content=prompt)])
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


async def invoke_supervisor(message: str) -> dict:
    """Invoke the supervisor with a user message (non-streaming)."""
    if not message or not message.strip():
        return {"answer": "请输入问题"}

    agent_name = classify_intent(message)

    if agent_name == "out_of_scope":
        return {"answer": OUT_OF_SCOPE_MESSAGE}

    try:
        if agent_name == "both":
            biz_state = {
                "messages": [HumanMessage(content=message)],
                "next_agent": "business_knowledge",
            }
            biz_result = business_knowledge_agent.invoke(biz_state, config=AGENT_CONFIG)
            biz_answer = _extract_answer(biz_result.get("messages", []))

            context_prefix = f"以下是相关的业务知识背景，请在分析时参考：\n{biz_answer}\n\n用户问题：{message}"
            data_state = {
                "messages": [HumanMessage(content=context_prefix)],
                "next_agent": "data_analysis",
            }
            data_result = data_analysis_agent.invoke(data_state, config=AGENT_CONFIG)
            answer = _extract_answer(data_result.get("messages", []))
            return {"answer": answer or "无法回答这个问题"}

        initial_state = {
            "messages": [HumanMessage(content=message)],
            "next_agent": agent_name,
        }

        agent = data_analysis_agent if agent_name == "data_analysis" else business_knowledge_agent
        result = agent.invoke(initial_state, config=AGENT_CONFIG)
        answer = _extract_answer(result.get("messages", []))
        return {"answer": answer or "无法回答这个问题"}

    except Exception as e:
        return {"answer": _handle_recursion_error(e)}


async def stream_supervisor(message: str) -> AsyncGenerator[dict, None]:
    """Stream supervisor events including tool calls and results."""
    if not message or not message.strip():
        yield {"type": "answer", "content": "请输入问题"}
        return

    agent_name = classify_intent(message)

    if agent_name == "out_of_scope":
        yield {"type": "answer", "content": OUT_OF_SCOPE_MESSAGE}
        return

    if agent_name == "both":
        biz_state = {
            "messages": [HumanMessage(content=message)],
            "next_agent": "business_knowledge",
        }
        biz_answer = ""
        try:
            async for event in business_knowledge_agent.astream_events(biz_state, version="v2", config=AGENT_CONFIG):
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
            "messages": [HumanMessage(content=context_prefix)],
            "next_agent": "data_analysis",
        }

        try:
            async for event in data_analysis_agent.astream_events(data_state, version="v2", config=AGENT_CONFIG):
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

            data_result = data_analysis_agent.invoke(data_state, config=AGENT_CONFIG)
            answer = _extract_answer(data_result.get("messages", []))
            yield {"type": "answer", "content": answer or "无法回答"}

        except Exception as e:
            yield {"type": "error", "content": _handle_recursion_error(e)}
        return

    initial_state = {
        "messages": [HumanMessage(content=message)],
        "next_agent": agent_name,
    }
    agent = data_analysis_agent if agent_name == "data_analysis" else business_knowledge_agent

    try:
        async for event in agent.astream_events(initial_state, version="v2", config=AGENT_CONFIG):
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

        result = agent.invoke(initial_state, config=AGENT_CONFIG)
        answer = _extract_answer(result.get("messages", []))
        yield {"type": "answer", "content": answer or "无法回答"}

    except Exception as e:
        yield {"type": "error", "content": _handle_recursion_error(e)}
