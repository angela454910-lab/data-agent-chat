"""Mock data layer: in-memory pandas DataFrames mimicking a real database."""

from __future__ import annotations

from datetime import date, timedelta
import pandas as pd

_TODAY = date(2026, 7, 8)


def _days_ago(n: int) -> str:
    return (_TODAY - timedelta(days=n)).isoformat()


# --- Dimension tables ---

channels_df = pd.DataFrame([
    {"id": "c_web", "name": "官网", "type": "owned"},
    {"id": "c_app", "name": "App", "type": "owned"},
    {"id": "c_ads", "name": "信息流广告", "type": "paid"},
    {"id": "c_live", "name": "直播", "type": "paid"},
])

products_df = pd.DataFrame([
    {"id": "p_basic", "name": "基础版", "category": "订阅"},
    {"id": "p_pro", "name": "专业版", "category": "订阅"},
    {"id": "p_enterprise", "name": "企业版", "category": "订阅"},
    {"id": "p_service", "name": "实施服务", "category": "服务"},
])

# --- Transaction tables ---

users_df = pd.DataFrame([
    {"id": "u_001", "signup_date": _days_ago(28), "region": "华东", "channel_id": "c_web", "converted": True},
    {"id": "u_002", "signup_date": _days_ago(27), "region": "华南", "channel_id": "c_ads", "converted": True},
    {"id": "u_003", "signup_date": _days_ago(24), "region": "华北", "channel_id": "c_app", "converted": False},
    {"id": "u_004", "signup_date": _days_ago(22), "region": "华东", "channel_id": "c_live", "converted": True},
    {"id": "u_005", "signup_date": _days_ago(18), "region": "西南", "channel_id": "c_ads", "converted": False},
    {"id": "u_006", "signup_date": _days_ago(16), "region": "华南", "channel_id": "c_app", "converted": True},
    {"id": "u_007", "signup_date": _days_ago(11), "region": "华东", "channel_id": "c_web", "converted": True},
    {"id": "u_008", "signup_date": _days_ago(8), "region": "华北", "channel_id": "c_live", "converted": False},
    {"id": "u_009", "signup_date": _days_ago(6), "region": "西南", "channel_id": "c_ads", "converted": True},
    {"id": "u_010", "signup_date": _days_ago(3), "region": "华南", "channel_id": "c_web", "converted": False},
])

orders_df = pd.DataFrame([
    {"id": "o_1001", "order_date": _days_ago(29), "user_id": "u_001", "channel_id": "c_web", "product_id": "p_pro", "region": "华东", "amount": 2980, "status": "paid", "refunded": False},
    {"id": "o_1002", "order_date": _days_ago(27), "user_id": "u_002", "channel_id": "c_ads", "product_id": "p_basic", "region": "华南", "amount": 980, "status": "paid", "refunded": False},
    {"id": "o_1003", "order_date": _days_ago(24), "user_id": "u_004", "channel_id": "c_live", "product_id": "p_enterprise", "region": "华东", "amount": 16800, "status": "paid", "refunded": False},
    {"id": "o_1004", "order_date": _days_ago(21), "user_id": "u_006", "channel_id": "c_app", "product_id": "p_pro", "region": "华南", "amount": 2980, "status": "paid", "refunded": True},
    {"id": "o_1005", "order_date": _days_ago(19), "user_id": "u_007", "channel_id": "c_web", "product_id": "p_service", "region": "华东", "amount": 5800, "status": "paid", "refunded": False},
    {"id": "o_1006", "order_date": _days_ago(17), "user_id": "u_009", "channel_id": "c_ads", "product_id": "p_pro", "region": "西南", "amount": 2980, "status": "paid", "refunded": False},
    {"id": "o_1007", "order_date": _days_ago(14), "user_id": "u_002", "channel_id": "c_ads", "product_id": "p_enterprise", "region": "华南", "amount": 16800, "status": "paid", "refunded": False},
    {"id": "o_1008", "order_date": _days_ago(12), "user_id": "u_001", "channel_id": "c_app", "product_id": "p_basic", "region": "华东", "amount": 980, "status": "paid", "refunded": False},
    {"id": "o_1009", "order_date": _days_ago(9), "user_id": "u_004", "channel_id": "c_live", "product_id": "p_service", "region": "华东", "amount": 5800, "status": "paid", "refunded": True},
    {"id": "o_1010", "order_date": _days_ago(7), "user_id": "u_006", "channel_id": "c_app", "product_id": "p_enterprise", "region": "华南", "amount": 16800, "status": "paid", "refunded": False},
    {"id": "o_1011", "order_date": _days_ago(5), "user_id": "u_009", "channel_id": "c_ads", "product_id": "p_basic", "region": "西南", "amount": 980, "status": "paid", "refunded": False},
    {"id": "o_1012", "order_date": _days_ago(2), "user_id": "u_007", "channel_id": "c_web", "product_id": "p_enterprise", "region": "华东", "amount": 16800, "status": "paid", "refunded": False},
])

# --- Table registry ---

TABLES: dict[str, pd.DataFrame] = {
    "orders": orders_df,
    "users": users_df,
    "channels": channels_df,
    "products": products_df,
}


def get_table(name: str) -> pd.DataFrame | None:
    return TABLES.get(name)


def list_table_names() -> list[str]:
    return list(TABLES.keys())
