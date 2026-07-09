"""Supervisor Agent: orchestrates multiple agents with streaming events."""

from __future__ import annotations

import json
from typing import TypedDict, AsyncGenerator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from app.agents.business_knowledge import business_knowledge_agent
from app.agents.data_analysis import data_analysis_agent


class AgentState(TypedDict):
    """State for the supervisor graph."""
    messages: list[BaseMessage]
    next_agent: str


def route_question(question: str) -> str:
    """Route question to appropriate agent based on keywords."""
    q = question.lower()

    business_keywords = ["政策", "定义", "怎么计算", "什么是", "说明", "规则", "如何", "标准",
                         "版本", "区别", "包含", "roi", "口径", "含义"]

    data_keywords = ["多少", "排名", "统计", "分析", "趋势", "对比", "最近", "销售额",
                     "订单量", "退款率", "转化率", "用户数", "地区", "渠道"]

    business_score = sum(1 for kw in business_keywords if kw in q)
    data_score = sum(1 for kw in data_keywords if kw in q)

    if business_score > data_score:
        return "business_knowledge"
    else:
        return "data_analysis"


async def invoke_supervisor(message: str) -> dict:
    """Invoke the supervisor with a user message (non-streaming)."""
    if not message or not message.strip():
        return {"answer": "请输入问题", "routed_to": "none"}

    agent_name = route_question(message)

    initial_state = {
        "messages": [HumanMessage(content=message)],
        "next_agent": agent_name,
    }

    if agent_name == "data_analysis":
        result = data_analysis_agent.invoke(initial_state)
    else:
        result = business_knowledge_agent.invoke(initial_state)

    messages = result.get("messages", [])
    ai_messages = [m for m in messages if isinstance(m, AIMessage)]

    if ai_messages:
        answer = ai_messages[-1].content
    else:
        answer = "无法回答这个问题"

    return {
        "answer": answer,
        "routed_to": agent_name,
    }


async def stream_supervisor(message: str) -> AsyncGenerator[dict, None]:
    """Stream supervisor events including thinking steps."""
    if not message or not message.strip():
        yield {"type": "answer", "content": "请输入问题"}
        yield {"type": "metadata", "routed_to": "none"}
        return

    # Step 1: Routing decision
    agent_name = route_question(message)
    yield {
        "type": "thinking",
        "step": "routing",
        "content": f"分析问题类型... 路由到 {'数据分析 Agent' if agent_name == 'data_analysis' else '业务知识 Agent'}"
    }

    yield {
        "type": "metadata",
        "routed_to": agent_name,
    }

    initial_state = {
        "messages": [HumanMessage(content=message)],
        "next_agent": agent_name,
    }

    agent = data_analysis_agent if agent_name == "data_analysis" else business_knowledge_agent

    try:
        async for event in agent.astream_events(initial_state, version="v2"):
            kind = event.get("event", "")

            # Tool calls
            if kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                yield {
                    "type": "tool_call",
                    "tool": tool_name,
                    "input": json.dumps(tool_input, ensure_ascii=False, indent=2) if isinstance(tool_input, dict) else str(tool_input)
                }

            # Tool results
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

        # Get final answer
        result = agent.invoke(initial_state)
        messages = result.get("messages", [])
        ai_messages = [m for m in messages if isinstance(m, AIMessage)]
        answer = ai_messages[-1].content if ai_messages else "无法回答"

        yield {"type": "answer", "content": answer}

    except Exception as e:
        yield {"type": "error", "content": f"处理出错: {str(e)}"}
