"""Business Knowledge Agent: answers business questions using RAG."""

from __future__ import annotations

from deepagents import create_deep_agent

from app.llm import get_chat_model
from app.knowledge.loader import get_knowledge_text

SYSTEM_PROMPT = """你是一个业务知识专家。你的职责是回答关于公司业务、产品、指标口径、政策规则等方面的问题。

## 业务知识库
{knowledge}

## 工作原则
1. 基于知识库中的信息回答问题
2. 如果知识库中没有相关信息，明确说明"知识库中没有相关信息"
3. 回答要准确、清晰，引用具体的政策或定义
4. 如果问题涉及数据分析，建议用户使用数据分析功能
""".format(knowledge=get_knowledge_text())

model = get_chat_model(temperature=0.1)
business_knowledge_agent = create_deep_agent(
    model=model,
    tools=[],
    system_prompt=SYSTEM_PROMPT,
)
