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
src/pipeline.py     the four pipeline steps as plain functions, plus a CLI
dbt/                dbt project: staging + mart models, schema and singular tests
dags/               Airflow DAG wiring the pipeline steps, scheduled daily
dashboard/          Streamlit app (app.py = layout, queries.py = warehouse reads)
data/               local raw/warehouse storage (git-ignored, kept via .gitkeep)
tests/              pytest suite across generator, ingestion, pipeline, dbt, dashboard
docs/               architecture notes + the day-7 PDF report
SESSION_LOG.md      daily progress log for this project
```

## Running it

```bash
pip install -r requirements.txt
python -m src.pipeline --count 1000      # generate -> ingest -> dbt run -> dbt test
streamlit run dashboard/app.py
```

Individual steps, if you want them separately:

```bash
python -m src.generator.event_generator --count 500 --days 14 --out data/raw/events.jsonl
python -m src.ingestion.ingest --source data/raw/events.jsonl
cd dbt && dbt build --profiles-dir .
```

The Airflow DAG (`dags/retailpulse_pipeline.py`) runs the same four steps on a
daily schedule — see [`dags/README.md`](dags/README.md). It needs Linux, WSL, or
Docker; Airflow has no native Windows support, which is exactly why the steps
live in `src/pipeline.py` and the DAG is only wiring.

## Data model

| Table | Grain | What it answers |
|---|---|---|
| `stg_events` | one event | typed, renamed view over `raw_events` |
| `stg_quarantined_events` | one rejected event | what failed validation, and why |
| `stg_pipeline_runs` | one ingest | batch row counts and reject rate |
| `daily_revenue` | date | revenue, purchases, purchasing users per day |
| `funnel_conversion` | session start date | view → cart → purchase counts and rates per day |
| `top_products` | date × product | purchases, units, revenue per product per day |

Marts sit at the finest useful grain so any window can be rolled up downstream;
an all-time table can only answer one question.

## Tests

```bash
python -m pytest tests/ -q
```

53 tests plus one that's skipped unless Airflow is installed. The suite covers
generator distributions and determinism, ingest validation/quarantine/
idempotency, the pipeline steps and their run auditing, a `dbt parse` guard, the
DAG's task wiring (at AST level, so it runs without Airflow), and the dashboard
queries against a real scratch warehouse.

## Status

See `SESSION_LOG.md` for day-by-day progress and `../../MEMORY.md` for the overall rotation this project fits into.
