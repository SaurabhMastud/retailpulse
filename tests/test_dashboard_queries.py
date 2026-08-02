"""Covers the dashboard's warehouse reads against a real, built warehouse.

Builds one scratch warehouse for the whole module (generate -> ingest -> dbt
run, via RETAILPULSE_WAREHOUSE) rather than mocking. These queries exist to be
right about mart shapes and window arithmetic; a mock would only assert that
the SQL string hasn't changed.
"""
import pytest

from dashboard import queries
from src import pipeline


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("dashboard_wh")
    wh = tmp / "retailpulse.duckdb"
    generated = pipeline.generate_step(count=600, days=10, seed=77, raw_dir=tmp, batch_id="t1")
    pipeline.ingest_step(generated["path"], warehouse=wh, batch_id="t1")
    pipeline.build_models(warehouse=wh)
    return wh


def test_daily_revenue_is_ordered_and_windowed(warehouse):
    rows = queries.daily_revenue(warehouse, days=5)
    assert not rows.empty
    assert list(rows["event_date"]) == sorted(rows["event_date"])
    # `> max_date - 5` keeps the newest day plus the 5 before it
    assert len(rows) <= 6


def test_daily_revenue_window_anchors_on_the_data_not_today(warehouse):
    # events are generated in the past, so a today-anchored window would be
    # empty for any small `days` -- this is the bug the anchor exists to avoid
    assert not queries.daily_revenue(warehouse, days=3).empty


def test_funnel_totals_recomputes_rates_from_summed_counts(warehouse):
    totals = queries.funnel_totals(warehouse, days=30)
    rows = queries.funnel(warehouse, days=30)

    assert totals["sessions"] == int(rows["total_sessions"].sum())
    # derived from the totals, not an average of per-day rates (which would
    # weight a quiet day the same as a busy one)
    assert totals["view_to_cart_rate"] == pytest.approx(
        totals["add_to_cart"] / totals["page_view"]
    )
    assert totals["view_to_cart_rate"] != pytest.approx(rows["view_to_cart_rate"].mean())


def test_funnel_totals_survives_an_empty_window(tmp_path):
    # a warehouse with marts but no rows in the window: rates degrade to None
    # instead of raising ZeroDivisionError in the app
    empty = tmp_path / "empty.duckdb"
    generated = pipeline.generate_step(count=5, days=1, seed=1, raw_dir=tmp_path, batch_id="e1")
    pipeline.ingest_step(generated["path"], warehouse=empty, batch_id="e1")
    pipeline.build_models(warehouse=empty)

    totals = queries.funnel_totals(empty, days=0)
    assert totals["view_to_cart_rate"] is None or totals["view_to_cart_rate"] >= 0


def test_top_products_rolls_up_the_daily_grain(warehouse):
    rows = queries.top_products(warehouse, days=30, limit=5)
    assert len(rows) <= 5
    assert rows["product_id"].is_unique, "daily rows should be collapsed per product"
    assert list(rows["gross_revenue"]) == sorted(rows["gross_revenue"], reverse=True)


def test_pipeline_runs_returns_the_audit_rows(warehouse):
    rows = queries.pipeline_runs(warehouse)
    assert not rows.empty
    assert {"batch_id", "events_read", "reject_rate"}.issubset(rows.columns)
