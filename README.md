# RetailPulse

A real-time-style retail analytics pipeline: simulated storefront events flow through an ingestion layer into a warehouse modeled with dbt, orchestrated by Airflow, and surfaced on a Streamlit dashboard.

**Domain:** Data Engineering · **Week:** 01 · **Started:** 2026-07-28

## Why this project

The modern data stack (event generation → streaming/batch ingestion → dbt-modeled warehouse → orchestration → BI) is the pattern most data engineering job reqs and blog posts are converging on right now — dbt for transformation-as-code, Airflow (or a lighter scheduler) for orchestration, and thin dashboards on top rather than heavyweight BI tools. RetailPulse builds a small, honest version of that full path end to end rather than a single link in the chain.

## Architecture (short version — see `docs/ARCHITECTURE.md` for the full writeup)

```
event generator  -->  raw landing zone  -->  staging models (dbt)  -->  mart models (dbt)  -->  dashboard (Streamlit)
      |                                              ^
      +---------------- orchestrated by Airflow -----+
```

## Project layout

```
src/generator/      synthetic e-commerce event generator
src/ingestion/      lands raw events (data/raw) into the warehouse (data/warehouse)
src/pipeline.py     the pipeline steps (incl. landing-zone replay) as plain functions, plus a CLI
dbt/                dbt project: product seed, staging + mart models, schema and singular tests
dags/               Airflow DAG wiring the pipeline steps, scheduled daily
dashboard/          Streamlit app (app.py = layout, queries.py = warehouse reads)
data/               local raw/warehouse storage (git-ignored, kept via .gitkeep)
tests/              pytest suite across generator, ingestion, pipeline, dbt, dashboard
docs/               architecture notes + the day-7 PDF report
```

## Running it

```bash
pip install -r requirements.txt
python -m src.pipeline --count 1000      # generate -> ingest -> dbt seed -> run -> test
streamlit run dashboard/app.py
```

Individual steps, if you want them separately:

```bash
python -m src.generator.event_generator --count 500 --days 14 --out data/raw/events.jsonl
python -m src.ingestion.ingest --source data/raw/events.jsonl
python -m src.generator.catalog          # re-export dbt/seeds/products.csv
cd dbt && dbt build --profiles-dir .
```

The Airflow DAG (`dags/retailpulse_pipeline.py`) runs the same steps on a
daily schedule — see [`dags/README.md`](dags/README.md). It needs Linux, WSL, or
Docker; Airflow has no native Windows support, which is exactly why the steps
live in `src/pipeline.py` and the DAG is only wiring.

## Rebuilding from raw

`data/raw/` is an append-only landing zone — one immutable file per batch,
named `events_<UTC timestamp>.jsonl`. The warehouse is disposable: delete it and
replay the landing zone to get it back.

```bash
rm data/warehouse/retailpulse.duckdb
python -m src.pipeline --replay                  # every batch, oldest first
python -m src.pipeline --replay --since 20260801 # or just a window
```

Replay is safe to run over a warehouse that already holds some of the batches —
ingestion upserts on `event_id`, so a re-run loads nothing and reports the
batches as duplicates. Each replayed batch writes its own `pipeline_runs` row,
dated when the replay ran; a replay is a real ingest and the audit table records
it as one rather than backdating it.

## Data model

| Table | Grain | What it answers |
|---|---|---|
| `products` (seed) | one product | the product dimension: category and list price, exported from `src/generator/catalog.py` |
| `stg_events` | one event | typed, renamed view over `raw_events` |
| `stg_quarantined_events` | one rejected event | what failed validation, and why |
| `stg_pipeline_runs` | one ingest | batch row counts and reject rate |
| `daily_revenue` | date | revenue, purchases, purchasing users per day |
| `funnel_conversion` | session start date | view → cart → purchase counts and rates per day |
| `top_products` | date × product | purchases, units, revenue per product per day (category joined from `products`) |

Marts sit at the finest useful grain so any window can be rolled up downstream;
an all-time table can only answer one question.

`products` is the single source of truth for what a product is. Events carry a
copy of `product_category`, but the marts join the dimension instead, and a dbt
test fails if the two ever disagree.

## Tests

```bash
python -m pytest tests/ -q
```

63 tests plus one that's skipped unless Airflow is installed. The suite covers
generator distributions and determinism, ingest validation/quarantine/
idempotency, the pipeline steps including landing-zone replay and their run
auditing, a `dbt parse` guard, the
DAG's task wiring (at AST level, so it runs without Airflow), and the dashboard
queries against a real scratch warehouse.

## Status

Built over a week of daily sessions. `docs/ARCHITECTURE.md` carries the
decisions log, written as the project went rather than reconstructed at the end.
