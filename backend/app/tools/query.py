"""Query tools for the data analysis agent.

These tools let the LLM query mock data via simple SQL-like operations
on pandas DataFrames. In production, replace with real DB queries.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from langchain_core.tools import tool

from app.schema.catalog import SCHEMA_CATALOG, get_schema_summary
from app.tools.mock_data import TABLES, get_table, list_table_names


def _apply_filters(df: pd.DataFrame, filters: dict[str, Any] | None) -> pd.DataFrame:
    """Apply filters to a DataFrame with support for scalar, list, and range values.

    - Scalar: exact match (==)
    - List: membership (isin)
    - Dict with keys gte/gt/lte/lt: range comparison (for numeric/date columns)

    Returns filtered DataFrame.
    """
    if not filters:
        return df

    result = df.copy()
    for col, val in filters.items():
        if col not in result.columns:
            continue

        if isinstance(val, dict):
            # Range filter: {"gte": 100, "lte": 500} or {"gte": "2026-06-21"}
            for op, threshold in val.items():
                if op == "gte":
                    result = result[result[col] >= threshold]
                elif op == "gt":
                    result = result[result[col] > threshold]
                elif op == "lte":
                    result = result[result[col] <= threshold]
                elif op == "lt":
                    result = result[result[col] < threshold]
        elif isinstance(val, list):
            # Membership filter: value in list
            result = result[result[col].isin(val)]
        else:
            # Exact match (scalar)
            result = result[result[col] == val]

    return result


@tool
def list_tables() -> str:
    """列出所有可用的数据表名称。"""
    return json.dumps(list_table_names(), ensure_ascii=False)


@tool
def describe_table(table_name: str) -> str:
    """获取指定表的字段信息和描述。

    Args:
        table_name: 表名，如 orders, users, channels, products
    """
    for t in SCHEMA_CATALOG:
        if t["name"] == table_name:
            fields_info = []
            for f in t["fields"]:
                aliases = f.get("aliases", [])
                alias_str = f" (别名: {', '.join(aliases)})" if aliases else ""
                fields_info.append(f"  - {f['name']} ({f['type']}): {f['title']}{alias_str}")
            return f"表: {t['title']} ({t['name']})\n描述: {t['description']}\n字段:\n" + "\n".join(fields_info)
    return f"表 {table_name} 不存在"


@tool
def query_data(table_name: str, columns: list[str] | None = None, filters: dict[str, Any] | None = None, limit: int = 100) -> str:
    """查询数据表，支持精确匹配、列表过滤和范围过滤。

    Args:
        table_name: 表名
        columns: 要返回的列名列表，None 表示全部
        filters: 过滤条件，支持三种格式：
            - 精确匹配: {"region": "华东"}
            - 列表匹配: {"channel_id": ["c_web", "c_app"]}
            - 范围过滤: {"order_date": {"gte": "2026-06-21", "lte": "2026-07-21"}}
            (gte=大于等于, gt=大于, lte=小于等于, lt=小于)
        limit: 返回行数上限
    """
    df = get_table(table_name)
    if df is None:
        return json.dumps({"error": f"表 {table_name} 不存在"}, ensure_ascii=False)

    result = _apply_filters(df, filters)

    # Select columns
    if columns:
        valid_cols = [c for c in columns if c in result.columns]
        if valid_cols:
            result = result[valid_cols]

    # Limit
    result = result.head(limit)

    return result.to_json(orient="records", force_ascii=False, indent=2)


@tool
def aggregate_data(table_name: str, group_by: str, agg_col: str, agg_func: str = "sum", filters: dict[str, Any] | None = None) -> str:
    """对数据进行分组聚合，支持精确匹配、列表过滤和范围过滤。

    Args:
        table_name: 表名
        group_by: 分组列名
        agg_col: 聚合列名
        agg_func: 聚合函数，支持 sum, mean, count, max, min
        filters: 过滤条件，支持三种格式：
            - 精确匹配: {"region": "华东"}
            - 列表匹配: {"channel_id": ["c_web", "c_app"]}
            - 范围过滤: {"order_date": {"gte": "2026-06-21", "lte": "2026-07-21"}}
            使用范围过滤可实现"最近30天"等时间范围查询
    """
    df = get_table(table_name)
    if df is None:
        return json.dumps({"error": f"表 {table_name} 不存在"}, ensure_ascii=False)

    result = _apply_filters(df, filters)

    if group_by not in result.columns or agg_col not in result.columns:
        return json.dumps({"error": "列名不存在"}, ensure_ascii=False)

    if agg_func == "count":
        grouped = result.groupby(group_by).size().reset_index(name="count")
    elif agg_func in ("sum", "mean", "max", "min"):
        grouped = result.groupby(group_by)[agg_col].agg(agg_func).reset_index()
    else:
        return json.dumps({"error": f"不支持的聚合函数: {agg_func}"}, ensure_ascii=False)

    sort_col = agg_col if agg_func != "count" else "count"
    grouped = grouped.sort_values(sort_col, ascending=False)
    return grouped.to_json(orient="records", force_ascii=False, indent=2)


@tool
def join_and_query(left_table: str, right_table: str, left_key: str, right_key: str, columns: list[str] | None = None, filters: dict[str, Any] | None = None, limit: int = 100) -> str:
    """关联两张表并查询，支持精确匹配、列表过滤和范围过滤。

    Args:
        left_table: 左表名
        right_table: 右表名
        left_key: 左表关联键
        right_key: 右表关联键
        columns: 要返回的列名列表
        filters: 过滤条件，支持三种格式：
            - 精确匹配: {"region": "华东"}
            - 列表匹配: {"channel_id": ["c_web", "c_app"]}
            - 范围过滤: {"order_date": {"gte": "2026-06-21", "lte": "2026-07-21"}}
        limit: 返回行数上限
    """
    left_df = get_table(left_table)
    right_df = get_table(right_table)

    if left_df is None or right_df is None:
        return json.dumps({"error": "表不存在"}, ensure_ascii=False)

    merged = left_df.merge(right_df, left_on=left_key, right_on=right_key, suffixes=(f"_{left_table}", f"_{right_table}"))

    merged = _apply_filters(merged, filters)

    if columns:
        valid_cols = [c for c in columns if c in merged.columns]
        if valid_cols:
            merged = merged[valid_cols]

    merged = merged.head(limit)
    return merged.to_json(orient="records", force_ascii=False, indent=2)


@tool
def get_schema_overview() -> str:
    """获取所有表的概览信息，包括表名、描述和字段列表。用于理解数据结构。"""
    summary = get_schema_summary()
    return json.dumps(summary, ensure_ascii=False, indent=2)


# All tools available to the data analysis agent
DATA_ANALYSIS_TOOLS = [
    list_tables,
    describe_table,
    query_data,
    aggregate_data,
    join_and_query,
    get_schema_overview,
]
