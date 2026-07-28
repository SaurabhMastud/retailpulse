# Streamlit dashboard (lands day 6)

Will read directly from the DuckDB warehouse's mart tables and render:
- daily revenue trend
- funnel conversion (page_view → add_to_cart → purchase)
- top products by revenue and by units sold

No app framework beyond Streamlit — this is a thin read-only view on top of the marts, not a product.
