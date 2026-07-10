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


ROUTING_PROMPT = """你是一个意图分类器。根据用户问题，判断应该由哪个 Agent 处理。

可选 Agent：
- business_knowledge: 业务概念、指标定义、政策规则、口径说明、计算方式等知识类问题
- data_analysis: 数据查询、统计分析、趋势对比、排名、具体数值等数据类问题
- both: 同时涉及知识问答和数据分析的混合问题（例如"退款率怎么算？最近30天是多少？"）

用户问题：{question}

只输出 JSON，不要输出其他内容：
{{"agent": "business_knowledge" | "data_analysis" | "both", "confidence": 0.0-1.0, "reason": "简要理由"}}"""


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
        if agent not in ("business_knowledge", "data_analysis", "both"):
            agent = "data_analysis"
        return agent
    except (json.JSONDecodeError, KeyError, Exception) as e:
        print(f"[Supervisor] Intent classification failed: {e}, falling back to data_analysis")
        return "data_analysis"


async def invoke_supervisor(message: str) -> dict:
    """Invoke the supervisor with a user message (non-streaming)."""
    if not message or not message.strip():
        return {"answer": "请输入问题"}

    agent_name = classify_intent(message)

    if agent_name == "both":
        biz_state = {
            "messages": [HumanMessage(content=message)],
            "next_agent": "business_knowledge",
        }
        biz_result = business_knowledge_agent.invoke(biz_state)
        biz_answer = ""
        for m in reversed(biz_result.get("messages", [])):
            if isinstance(m, AIMessage):
                biz_answer = m.content
                break

        context_prefix = f"以下是相关的业务知识背景，请在分析时参考：\n{biz_answer}\n\n用户问题：{message}"
        data_state = {
            "messages": [HumanMessage(content=context_prefix)],
            "next_agent": "data_analysis",
        }
        data_result = data_analysis_agent.invoke(data_state)
        answer = ""
        for m in reversed(data_result.get("messages", [])):
            if isinstance(m, AIMessage):
                answer = m.content
                break

        return {"answer": answer or "无法回答这个问题"}

    initial_state = {
        "messages": [HumanMessage(content=message)],
        "next_agent": agent_name,
    }

    agent = data_analysis_agent if agent_name == "data_analysis" else business_knowledge_agent
    result = agent.invoke(initial_state)

    answer = ""
    for m in reversed(result.get("messages", [])):
        if isinstance(m, AIMessage):
            answer = m.content
            break

    return {"answer": answer or "无法回答这个问题"}


async def stream_supervisor(message: str) -> AsyncGenerator[dict, None]:
    """Stream supervisor events including tool calls and results."""
    if not message or not message.strip():
        yield {"type": "answer", "content": "请输入问题"}
        yield "data: [DONE]\n\n"
        return

    agent_name = classify_intent(message)

    if agent_name == "both":
        biz_state = {
            "messages": [HumanMessage(content=message)],
            "next_agent": "business_knowledge",
        }
        biz_answer = ""
        try:
            async for event in business_knowledge_agent.astream_events(biz_state, version="v2"):
                kind = event.get("event", "")
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield {"type": "sub_answer", "content": chunk.content}
                        biz_answer += chunk.content
        except Exception as e:
            yield {"type": "error", "content": f"业务知识处理出错: {str(e)}"}

        context_prefix = f"以下是相关的业务知识背景，请在分析时参考：\n{biz_answer}\n\n用户问题：{message}"
        data_state = {
            "messages": [HumanMessage(content=context_prefix)],
            "next_agent": "data_analysis",
        }

        try:
            async for event in data_analysis_agent.astream_events(data_state, version="v2"):
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
                    output_str = str(tool_output)
                    if len(output_str) > 500:
                        output_str = output_str[:500] + "..."
                    yield {
                        "type": "tool_result",
                        "tool": tool_name,
                        "output": output_str
                    }

            data_result = data_analysis_agent.invoke(data_state)
            answer = ""
            for m in reversed(data_result.get("messages", [])):
                if isinstance(m, AIMessage):
                    answer = m.content
                    break
            yield {"type": "answer", "content": answer or "无法回答"}

        except Exception as e:
            yield {"type": "error", "content": f"数据分析处理出错: {str(e)}"}
        return

    initial_state = {
        "messages": [HumanMessage(content=message)],
        "next_agent": agent_name,
    }
    agent = data_analysis_agent if agent_name == "data_analysis" else business_knowledge_agent

    try:
        async for event in agent.astream_events(initial_state, version="v2"):
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
                output_str = str(tool_output)
                if len(output_str) > 500:
                    output_str = output_str[:500] + "..."
                yield {
                    "type": "tool_result",
                    "tool": tool_name,
                    "output": output_str
                }

        result = agent.invoke(initial_state)
        answer = ""
        for m in reversed(result.get("messages", [])):
            if isinstance(m, AIMessage):
                answer = m.content
                break

        yield {"type": "answer", "content": answer or "无法回答"}

    except Exception as e:
        yield {"type": "error", "content": f"处理出错: {str(e)}"}
