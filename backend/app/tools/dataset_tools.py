"""Dataset tools: query/aggregate the user-uploaded session dataset and analyze YOLO results.

These tools operate on the DataFrame stored in the per-session dataset store,
and also provide YOLO detection result analysis capabilities.
They use the contextvar set by the supervisor at the start of each request,
so they have no explicit session_id parameter -- the right dataset is resolved
 automatically from the current request context.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from langchain_core.tools import tool

from app.session.dataset import get_dataset
from app.tools.yolo_analysis import analyze_yolo_content


def _apply_filters(df: pd.DataFrame, filters: dict[str, Any] | None) -> pd.DataFrame:
    if not filters:
        return df
    result = df.copy()
    for col, val in filters.items():
        if col not in result.columns:
            continue
        if isinstance(val, dict):
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
            result = result[result[col].isin(val)]
        else:
            result = result[result[col] == val]
    return result


@tool
def describe_dataset() -> str:
    """Describe the user-uploaded dataset: column names, types, sample values, and row count.
    Call this first when the user asks about their uploaded data to understand its structure.
    Returns 'No dataset uploaded' if the session has no uploaded file.
    """
    entry = get_dataset()
    if entry is None:
        return "No dataset uploaded for this session. Ask the user to upload an Excel or JSON file."
    return entry.schema_text()


@tool
def query_dataset(
    columns: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    limit: int = 100,
) -> str:
    """Query the user-uploaded dataset with optional column selection and filtering.

    Args:
        columns: Column names to return. None = all columns.
        filters: Filter conditions, same format as query_data:
            - Exact: {"region": "East"}
            - List: {"channel": ["web", "app"]}
            - Range: {"date": {"gte": "2026-01-01", "lte": "2026-03-31"}}
        limit: Max rows to return (default 100).
    """
    entry = get_dataset()
    if entry is None:
        return "No dataset uploaded for this session."
    df = _apply_filters(entry.df, filters)
    if columns:
        valid = [c for c in columns if c in df.columns]
        if valid:
            df = df[valid]
    df = df.head(limit)
    return df.to_json(orient="records", force_ascii=False, indent=2)


@tool
def aggregate_dataset(
    group_by: str,
    agg_col: str,
    agg_func: str = "sum",
    filters: dict[str, Any] | None = None,
) -> str:
    """Aggregate the user-uploaded dataset by a column.

    Args:
        group_by: Column to group by.
        agg_col: Column to aggregate.
        agg_func: Aggregation function: sum, mean, count, max, min.
        filters: Optional filter conditions (same format as query_dataset).
    """
    entry = get_dataset()
    if entry is None:
        return "No dataset uploaded for this session."
    df = _apply_filters(entry.df, filters)
    if group_by not in df.columns or agg_col not in df.columns:
        return json.dumps(
            {"error": f"Column not found. Available: {list(df.columns)}"},
            ensure_ascii=False,
        )
    if agg_func == "count":
        grouped = df.groupby(group_by).size().reset_index(name="count")
    elif agg_func in ("sum", "mean", "max", "min"):
        grouped = df.groupby(group_by)[agg_col].agg(agg_func).reset_index()
    else:
        return json.dumps({"error": f"Unsupported agg_func: {agg_func}"}, ensure_ascii=False)
    sort_col = agg_col if agg_func != "count" else "count"
    grouped = grouped.sort_values(sort_col, ascending=False)
    return grouped.to_json(orient="records", force_ascii=False, indent=2)


@tool
def analyze_yolo_results(yolo_content: str, confidence_threshold: float = 0.5) -> str:
    """Analyze YOLO shelf detection results.

    This tool processes YOLO object detection output from shelf images,
    providing structured data about product counts, competitor analysis,
    price tag detection, and layout analysis.

    Args:
        yolo_content: Raw YOLO detection result string containing boxes array
        confidence_threshold: Minimum confidence score for valid detections (default: 0.5)

    Returns:
        JSON string with structured analysis results
    """
    try:
        result = analyze_yolo_content(yolo_content, confidence_threshold)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


DATASET_TOOLS = [describe_dataset, query_dataset, aggregate_dataset, analyze_yolo_results]
