# dbt project (lands day 3-4)

Will hold:
- `dbt_project.yml` + a DuckDB profile pointed at `../data/warehouse/retailpulse.duckdb`
- `models/staging/` — typed, deduped views over `raw_events`
- `models/marts/` — `daily_revenue`, `funnel_conversion`, `top_products`
- `tests/` (dbt schema + custom tests) for null/uniqueness/accepted-values checks on the marts

Kept as an empty skeleton today so the folder structure in `docs/ARCHITECTURE.md` matches the repo from day 1 onward.
