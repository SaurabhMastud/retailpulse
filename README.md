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
src/generator/     synthetic e-commerce event generator
src/ingestion/      lands raw events (data/raw) into the warehouse (data/warehouse)
dbt/                dbt project: staging + mart models
dags/               Airflow DAGs orchestrating generate -> ingest -> transform
dashboard/          Streamlit app reading from the warehouse
data/               local raw/warehouse storage (git-ignored, kept via .gitkeep)
tests/              unit tests for generator/ingestion logic
docs/               architecture notes + the day-7 PDF report
SESSION_LOG.md      daily progress log for this project
```

## Running it (day 1 slice)

```bash
pip install -r requirements.txt
python -m src.generator.event_generator --count 500 --out data/raw/events.jsonl
python -m src.ingestion.ingest --source data/raw/events.jsonl
```

## Status

See `SESSION_LOG.md` for day-by-day progress and `../../MEMORY.md` for the overall rotation this project fits into.
