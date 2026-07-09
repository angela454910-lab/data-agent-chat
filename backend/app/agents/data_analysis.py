"""Data Analysis Agent: uses LLM + tools to answer data queries."""

from __future__ import annotations

from deepagents import create_deep_agent

from app.llm import get_chat_model
from app.tools.query import DATA_ANALYSIS_TOOLS

SYSTEM_PROMPT = """你是一个专业的数据分析师 Agent。你的职责是帮助用户查询和分析业务数据。

## 工作原则
1. 先理解用户问题，确定需要查询哪些表、哪些字段
2. 使用工具查询数据，支持简单查询、聚合统计、表关联
3. 基于查询结果生成清晰的分析结论
4. 如果数据不足以回答问题，明确说明

## 注意事项
- 当前日期是 2026-07-08
- 金额单位是人民币（¥）
- 如果用户问"最近 N 天"，根据当前日期计算时间范围
- 退款率 = 退款订单数 / 总订单数
- 转化率 = 已转化用户数 / 总用户数
"""

model = get_chat_model(temperature=0.1)
data_analysis_agent = create_deep_agent(
    model=model,
    tools=DATA_ANALYSIS_TOOLS,
    system_prompt=SYSTEM_PROMPT,
)
