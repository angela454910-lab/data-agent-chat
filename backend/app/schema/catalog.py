"""Schema catalog: table/field/metric definitions for the data agent."""

from __future__ import annotations

SCHEMA_CATALOG: list[dict] = [
    {
        "name": "orders",
        "title": "订单表",
        "description": "记录订单、收入、退款、地区、渠道和商品。",
        "keywords": ["订单", "销售额", "收入", "成交", "退款", "客单价", "地区", "渠道", "商品"],
        "fields": [
            {"name": "id", "title": "订单ID", "type": "string"},
            {"name": "order_date", "title": "下单日期", "type": "date", "aliases": ["时间", "日期", "最近"]},
            {"name": "user_id", "title": "用户ID", "type": "string"},
            {"name": "channel_id", "title": "渠道ID", "type": "string", "relation": "channels.id"},
            {"name": "product_id", "title": "商品ID", "type": "string", "relation": "products.id"},
            {"name": "region", "title": "地区", "type": "string", "aliases": ["区域", "省区"]},
            {"name": "amount", "title": "订单金额", "type": "number", "aliases": ["销售额", "收入", "GMV", "金额"]},
            {"name": "status", "title": "订单状态", "type": "string"},
            {"name": "refunded", "title": "是否退款", "type": "boolean", "aliases": ["退款率", "退款"]},
        ],
    },
    {
        "name": "users",
        "title": "用户表",
        "description": "记录新用户、注册时间、来源渠道、地区和是否转化。",
        "keywords": ["用户", "新用户", "注册", "转化", "转化率", "地区", "渠道"],
        "fields": [
            {"name": "id", "title": "用户ID", "type": "string"},
            {"name": "signup_date", "title": "注册日期", "type": "date", "aliases": ["注册时间", "新增时间"]},
            {"name": "region", "title": "地区", "type": "string"},
            {"name": "channel_id", "title": "渠道ID", "type": "string", "relation": "channels.id"},
            {"name": "converted", "title": "是否转化", "type": "boolean", "aliases": ["转化率", "成交用户"]},
        ],
    },
    {
        "name": "channels",
        "title": "渠道表",
        "description": "记录渠道名称和渠道类型。",
        "keywords": ["渠道", "来源", "投放", "广告", "直播", "官网", "App"],
        "fields": [
            {"name": "id", "title": "渠道ID", "type": "string"},
            {"name": "name", "title": "渠道名称", "type": "string"},
            {"name": "type", "title": "渠道类型", "type": "string"},
        ],
    },
    {
        "name": "products",
        "title": "商品表",
        "description": "记录商品名称和商品分类。",
        "keywords": ["商品", "产品", "品类", "订阅", "服务"],
        "fields": [
            {"name": "id", "title": "商品ID", "type": "string"},
            {"name": "name", "title": "商品名称", "type": "string"},
            {"name": "category", "title": "商品分类", "type": "string"},
        ],
    },
]

METRIC_DICTIONARY: list[dict] = [
    {"name": "revenue", "title": "销售额", "keywords": ["销售额", "收入", "GMV", "金额"], "table": "orders"},
    {"name": "order_count", "title": "订单数", "keywords": ["订单数", "订单量", "成交量"], "table": "orders"},
    {"name": "refund_rate", "title": "退款率", "keywords": ["退款率", "退款"], "table": "orders"},
    {"name": "new_users", "title": "新用户数", "keywords": ["新用户", "新增用户", "注册"], "table": "users"},
    {"name": "conversion_rate", "title": "转化率", "keywords": ["转化率", "转化"], "table": "users"},
]


def get_schema_summary() -> list[dict]:
    """Return a simplified schema summary for LLM context."""
    return [
        {
            "name": t["name"],
            "title": t["title"],
            "description": t["description"],
            "fields": [
                {"name": f["name"], "title": f["title"], "type": f["type"]}
                for f in t["fields"]
            ],
        }
        for t in SCHEMA_CATALOG
    ]


def get_full_schema_text() -> str:
    """Return full schema as formatted text for LLM prompt."""
    lines = ["# 数据表 Schema\n"]
    for table in SCHEMA_CATALOG:
        lines.append(f"## {table['title']} ({table['name']})")
        lines.append(f"描述: {table['description']}")
        lines.append("字段:")
        for f in table["fields"]:
            aliases = f.get("aliases", [])
            alias_str = f" (别名: {', '.join(aliases)})" if aliases else ""
            relation = f" -> {f['relation']}" if "relation" in f else ""
            lines.append(f"  - {f['name']} ({f['type']}): {f['title']}{alias_str}{relation}")
        lines.append("")

    lines.append("# 指标定义\n")
    for m in METRIC_DICTIONARY:
        lines.append(f"- {m['title']} ({m['name']}): 关键词 [{', '.join(m['keywords'])}], 来源表: {m['table']}")

    return "\n".join(lines)
