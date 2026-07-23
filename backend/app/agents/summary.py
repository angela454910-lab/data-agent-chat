"""Session summary agent: generates a concise summary of a chat conversation."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from app.llm import get_chat_model

SUMMARY_PROMPT = """你是一个会话总结助手。以下是一个用户与数据分析助手的完整对话记录。
请用 2-3 句话总结本次会话的核心内容，包括：
- 用户的主要分析目标
- 涉及了哪些数据维度（如时间范围、地区、渠道等）
- 关键发现或结论

要求简洁、有结论性，不要罗列每条消息。直接输出总结文本，不要加前缀。

对话记录：
{conversation}
"""


def _format_conversation(messages: list[dict]) -> str:
    lines: list[str] = []
    for msg in messages:
        role = "用户" if msg.get("role") == "user" else "助手"
        content = msg.get("content", "")
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def generate_summary(messages: list[dict]) -> str:
    """Generate a session summary from conversation messages."""
    if not messages:
        return ""
    conversation = _format_conversation(messages)
    if not conversation.strip():
        return ""

    model = get_chat_model(temperature=0.3)
    prompt = SUMMARY_PROMPT.format(conversation=conversation)
    try:
        response = model.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception as e:
        print(f"[Summary] Generation failed: {e}")
        return ""
