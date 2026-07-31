"""RetailPulse dashboard -- a read-only view on the dbt marts.

Layout only. Every warehouse read lives in dashboard/queries.py, which is
where the tests are. Run with:

    streamlit run dashboard/app.py
"""
from pathlib import Path

import streamlit as st

from dashboard import queries

st.set_page_config(page_title="RetailPulse", page_icon="🛒", layout="wide")

st.title("RetailPulse")
st.caption("Synthetic retail analytics — generator → DuckDB → dbt marts → here.")

if not Path(queries.DEFAULT_WAREHOUSE).exists():
    st.error(
        "No warehouse found. Run the pipeline first:\n\n"
        "```\npython -m src.pipeline --count 1000\n```"
    )
    st.stop()

window = st.sidebar.slider("Window (days)", min_value=3, max_value=30, value=14)

revenue = queries.daily_revenue(days=window)
totals = queries.funnel_totals(days=window)

if revenue.empty:
    st.warning("The marts are empty. Run `python -m src.pipeline` to load a batch.")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Gross revenue", f"${revenue['gross_revenue'].sum():,.0f}")
col2.metric("Purchases", f"{int(revenue['num_purchases'].sum()):,}")
col3.metric("Sessions", f"{totals['sessions']:,}")
col4.metric(
    "Session → purchase",
    f"{totals['purchase'] / totals['sessions']:.1%}" if totals["sessions"] else "—",
)

st.subheader("Daily revenue")
st.line_chart(revenue.set_index("event_date")["gross_revenue"])

left, right = st.columns(2)

with left:
    st.subheader("Funnel")
    st.bar_chart(
        {
            "sessions": [totals["page_view"], totals["add_to_cart"], totals["purchase"]],
        },
        x_label="stage",
    )
    st.caption(
        f"view → cart {totals['view_to_cart_rate']:.1%} · "
        f"cart → purchase {totals['cart_to_purchase_rate']:.1%}"
        if totals["view_to_cart_rate"] and totals["cart_to_purchase_rate"]
        else "not enough data for conversion rates"
    )

with right:
    st.subheader("Conversion rate by day")
    funnel_by_day = queries.funnel(days=window)
    st.line_chart(
        funnel_by_day.set_index("session_date")[["view_to_cart_rate", "cart_to_purchase_rate"]]
    )

st.subheader("Top products")
st.dataframe(queries.top_products(days=window, limit=10), width="stretch")

st.subheader("Pipeline runs")
runs = queries.pipeline_runs()
st.dataframe(runs, width="stretch")
if not runs.empty and runs["reject_rate"].max() > 0:
    st.warning(f"Highest reject rate in recent runs: {runs['reject_rate'].max():.2%}")
