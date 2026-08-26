"""YOLO Analysis Agent: analyzes YOLO shelf detection results.

This is a dedicated agent for YOLO detection result analysis only.
"""

from __future__ import annotations

from deepagents import create_deep_agent

from app.llm import get_chat_model
from app.tools.yolo_analysis import YOLO_TOOLS

SYSTEM_PROMPT = """你是一个专业的货架检测分析助手，专注于分析 YOLO 目标检测结果。

主要任务：
1. 解析 YOLO 检测结果
2. 分析主要产品和竞品的数量、位置关系
3. 分析价格标签与产品的对应关系
4. 分析货架布局情况（中心区域、面积占比等）
5. 基于分析结果给出陈列优化和销售建议

分析要点：
- 区分主要产品（高置信度）和竞品（低置信度）
- 关注价格标签的识别和与产品的对应关系
- 分析产品在货架上的布局和位置
- 结合具体数据给出可验证的结论和建议

工作流程：
- 如果用户提供了 YOLO 检测结果，优先调用 `analyze_yolo_results` 工具进行分析
- 获取到结构化数据后，进行深入分析并给出具体建议
- 回答中引用具体数字，让结论可验证

注意：
- 只处理 YOLO 货架检测相关的问题
- 不需要处理表格数据、Excel/JSON 文件等其他内容
"""

model = get_chat_model(temperature=0.1, streaming=True)
yolo_analysis_agent = create_deep_agent(
    model=model,
    tools=YOLO_TOOLS,
    system_prompt=SYSTEM_PROMPT,
)
