"""Warehouse reads for the dashboard, kept out of the Streamlit app.

Streamlit's rendering is painful to test; SQL against a warehouse is not. Every
query lives here as a plain function returning a DataFrame, so the app file
stays layout-only and the logic that could actually be wrong is covered by
tests/test_dashboard_queries.py.

All reads are read-only -- the dashboard never writes to the warehouse, which
also means it can't lock out a concurrent pipeline run.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WAREHOUSE = PROJECT_ROOT / "data" / "warehouse" / "retailpulse.duckdb"


@contextmanager
def connect(warehouse: str | Path = DEFAULT_WAREHOUSE):
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        yield con
    finally:
        con.close()


def _query(warehouse: str | Path, sql: str, params: list | None = None) -> pd.DataFrame:
    with connect(warehouse) as con:
        return con.execute(sql, params or []).df()


def daily_revenue(warehouse: str | Path = DEFAULT_WAREHOUSE, days: int = 14) -> pd.DataFrame:
    """Revenue per day over the last `days` days of data present in the mart.

    Windowed off the newest date in the data, not today's date -- a generated
    batch can end a day or two short, and anchoring on today would render an
    empty chart in that case.
    """
    return _query(
        warehouse,
        """
        select *
        from daily_revenue
        where event_date > (select max(event_date) from daily_revenue) - cast(? as integer)
        order by event_date
        """,
        [days],
    )


def funnel(warehouse: str | Path = DEFAULT_WAREHOUSE, days: int = 14) -> pd.DataFrame:
    return _query(
        warehouse,
        """
        select *
        from funnel_conversion
        where session_date > (select max(session_date) from funnel_conversion) - cast(? as integer)
        order by session_date
        """,
        [days],
    )


def funnel_totals(warehouse: str | Path = DEFAULT_WAREHOUSE, days: int = 14) -> dict:
    """Collapse the daily funnel into one set of stage counts and rates.

    Rates are recomputed from the summed counts rather than averaged across
    days -- averaging per-day rates would weight a quiet day the same as a busy
    one and give a number that doesn't match the totals shown beside it.
    """
    rows = funnel(warehouse, days=days)
    if rows.empty:
        return {"sessions": 0, "page_view": 0, "add_to_cart": 0, "purchase": 0,
                "view_to_cart_rate": None, "cart_to_purchase_rate": None}

    page_view = int(rows["sessions_with_page_view"].sum())
    add_to_cart = int(rows["sessions_with_add_to_cart"].sum())
    purchase = int(rows["sessions_with_purchase"].sum())
    return {
        "sessions": int(rows["total_sessions"].sum()),
        "page_view": page_view,
        "add_to_cart": add_to_cart,
        "purchase": purchase,
        "view_to_cart_rate": add_to_cart / page_view if page_view else None,
        "cart_to_purchase_rate": purchase / add_to_cart if add_to_cart else None,
    }


def top_products(
    warehouse: str | Path = DEFAULT_WAREHOUSE, days: int = 14, limit: int = 10
) -> pd.DataFrame:
    """Top products by revenue, rolled up from the daily grain over the window."""
    return _query(
        warehouse,
        """
        select
            product_id,
            product_category,
            sum(num_purchases) as num_purchases,
            sum(units_sold) as units_sold,
            sum(gross_revenue) as gross_revenue
        from top_products
        where event_date > (select max(event_date) from top_products) - cast(? as integer)
        group by product_id, product_category
        order by gross_revenue desc
        limit ?
        """,
        [days, limit],
    )


def pipeline_runs(warehouse: str | Path = DEFAULT_WAREHOUSE, limit: int = 20) -> pd.DataFrame:
    return _query(
        warehouse,
        """
        select batch_id, events_read, events_loaded, duplicates, rejected, reject_rate, ingested_at
        from stg_pipeline_runs
        order by ingested_at desc
        limit ?
        """,
        [limit],
    )
