# dbt project

`dbt_project.yml` + `profiles.yml` (kept in-repo instead of `~/.dbt/` for portability) point the `retailpulse` profile at `../data/warehouse/retailpulse.duckdb`. Run any dbt command from this directory with `--profiles-dir .`, e.g.:

```
dbt debug --profiles-dir .
dbt seed --profiles-dir .
dbt run --profiles-dir .
```

Contents:
- `seeds/products.csv` — the product dimension, **generated** by `python -m src.generator.catalog`; don't edit it by hand
- `models/staging/` — typed, deduped views over `raw_events`
- `models/marts/` — `daily_revenue`, `funnel_conversion`, `top_products`
- `tests/` (dbt schema + custom tests) for null/uniqueness/accepted-values checks on the marts
