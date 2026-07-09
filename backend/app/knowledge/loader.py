"""Business knowledge base: mock documents for RAG."""

from __future__ import annotations

# Mock business knowledge documents
BUSINESS_KNOWLEDGE = [
    {
        "id": "k001",
        "title": "退款政策",
        "content": "我们的退款政策：订单支付后 7 天内可申请全额退款。超过 7 天按剩余服务期比例退款。订阅类商品按月折算，服务类商品按工时折算。退款审批需主管签字，金额超过 5000 元需总监审批。",
        "category": "政策",
    },
    {
        "id": "k002",
        "title": "渠道 ROI 计算方法",
        "content": "渠道 ROI = 该渠道带来的有效收入 / 该渠道投入成本。有效收入需排除退款订单。投入成本包括广告费、人力成本、平台佣金等。信息流广告按 CPC 计费，直播渠道按坑位费 + 佣金计算。ROI > 1 表示盈利，ROI > 3 表示优秀。",
        "category": "指标口径",
    },
    {
        "id": "k003",
        "title": "商品版本对比",
        "content": "基础版：¥980/年，适合个人用户，包含核心功能。专业版：¥2980/年，适合小团队，包含高级功能和优先支持。企业版：¥16800/年，适合大企业，包含定制开发、专属客户经理、SLA 保障。实施服务：¥5800/次，包含系统部署、培训、数据迁移。",
        "category": "产品",
    },
    {
        "id": "k004",
        "title": "转化率定义",
        "content": "转化率 = 已转化用户数 / 注册用户数。已转化用户指注册后 30 天内完成首次付费的用户。转化率按渠道、地区、时间段可以拆分分析。行业平均转化率约 15-25%，我们的目标转化率是 30%。",
        "category": "指标口径",
    },
    {
        "id": "k005",
        "title": "客单价计算",
        "content": "客单价 = 有效销售额 / 有效订单数。有效销售额需排除退款订单。客单价可以按渠道、商品、地区拆分。客单价反映用户的平均消费水平，是衡量用户价值的重要指标。",
        "category": "指标口径",
    },
    {
        "id": "k006",
        "title": "渠道类型说明",
        "content": "自有渠道（owned）：官网、App，无直接获客成本，用户主动访问。付费渠道（paid）：信息流广告、直播，需要投入广告费或佣金。自有渠道的 ROI 通常更高，但付费渠道可以快速扩大规模。",
        "category": "业务规则",
    },
    {
        "id": "k007",
        "title": "地区划分",
        "content": "我们的地区划分为：华东（上海、江苏、浙江）、华南（广东、福建）、华北（北京、天津、河北）、西南（四川、重庆、云南）。不同地区的用户偏好和转化率有差异，华东和华南是核心市场。",
        "category": "业务规则",
    },
    {
        "id": "k008",
        "title": "订单状态说明",
        "content": "订单状态：pending（待支付）、paid（已支付）、cancelled（已取消）、refunded（已退款）。只有 paid 状态的订单才计入有效销售额。refunded 标记为 True 的订单虽然状态是 paid，但已退款，需从有效收入中扣除。",
        "category": "业务规则",
    },
]


def load_knowledge_documents() -> list[dict]:
    """Return all business knowledge documents."""
    return BUSINESS_KNOWLEDGE


def get_knowledge_text() -> str:
    """Return all knowledge as formatted text."""
    lines = []
    for doc in BUSINESS_KNOWLEDGE:
        lines.append(f"## {doc['title']} ({doc['category']})")
        lines.append(doc["content"])
        lines.append("")
    return "\n".join(lines)
