# Streamlit dashboard

A read-only view on the dbt marts. No app framework beyond Streamlit — this is
a thin window onto the warehouse, not a product.

```bash
python -m src.pipeline --count 1000    # build the marts first
streamlit run dashboard/app.py
```

## Layout

- headline metrics: gross revenue, purchases, sessions, session → purchase rate
- daily revenue trend (`daily_revenue`)
- funnel stage counts and per-day conversion rates (`funnel_conversion`)
- top products by revenue over the selected window (`top_products`, rolled up
  from its daily grain)
- recent pipeline runs and reject rates (`stg_pipeline_runs`), so a bad batch
  is visible next to the numbers it affected

A sidebar slider sets the window in days.

## Why queries.py is a separate module

`app.py` is layout only; every warehouse read lives in `queries.py`. Streamlit
rendering is awkward to test, SQL is not — so the logic that can actually be
wrong (window arithmetic, rate derivation, roll-ups) is covered by
`tests/test_dashboard_queries.py` against a real built warehouse, and
`tests/test_dashboard_app.py` renders the app itself through Streamlit's
`AppTest` to catch layout calls that raise.

Windows are anchored on the newest date present in the marts rather than on
today, because generated batches often end a day or two short — anchoring on
today renders an empty chart.
