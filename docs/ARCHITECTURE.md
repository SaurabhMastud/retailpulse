# Architecture — RetailPulse

## Why this project

Data engineering job postings and modern-data-stack writeups keep converging on the same shape: an event source, a landing zone, transformation-as-code (dbt), an orchestrator, and a thin consumption layer. RetailPulse is a small but complete pass through that whole shape rather than a demo of one link in the chain, using synthetic retail/e-commerce events as the domain because it produces intuitive, easy-to-validate analytics (revenue, conversion, top products) without needing a real data source.

## Components

| Component | Tool | Role |
|---|---|---|
| Event generator | Python (`src/generator`) | Produces synthetic e-commerce events (page views, add-to-cart, purchases) as JSON lines — stands in for a real event stream (Kafka/Segment/etc.) |
| Landing zone | Local filesystem (`data/raw`) | Immutable raw event storage, one file per batch |
| Ingestion | Python (`src/ingestion`) | Reads raw events, validates/normalizes schema, loads into the warehouse (`data/warehouse`, DuckDB) |
| Warehouse | DuckDB | Lightweight embedded warehouse — no server to run, plays well with dbt, good enough for this scale |
| Transformation | dbt (`dbt/`) | Staging models (clean/typed events) → mart models (daily revenue, funnel conversion, top products) |
| Orchestration | Airflow (`dags/`) | DAG: generate → ingest → dbt run → dbt test, scheduled daily |
| Consumption | Streamlit (`dashboard/`) | Reads mart tables, renders revenue/funnel/product charts |

## Data flow

```
event_generator.py --> data/raw/*.jsonl --> ingest.py --> data/warehouse/retailpulse.duckdb (raw_events table)
                                                                    |
                                                          dbt staging models (typed, deduped)
                                                                    |
                                                          dbt mart models (daily_revenue, funnel, top_products)
                                                                    |
                                                          Streamlit dashboard
```

## Event schema (raw)

```json
{
  "event_id": "uuid",
  "event_type": "page_view | add_to_cart | purchase",
  "user_id": "string",
  "session_id": "uuid, shared by all events in one browsing session",
  "product_id": "string",
  "product_category": "string",
  "price": "float, present on add_to_cart/purchase",
  "quantity": "int, present on add_to_cart/purchase",
  "timestamp": "ISO-8601 UTC"
}
```

Events are generated in sessions (1-4 events, same user, clustered timestamps) rather than as independent draws -- `session_id` is what will let the day-4 `funnel_conversion` mart group page_view → add_to_cart → purchase per visit instead of per random event.

## Day-by-day plan

| Day | Focus |
|---|---|
| 1 | Scaffolding, architecture doc, event generator, raw ingestion into DuckDB, tests |
| 2 | Ingestion hardening (schema validation, batching), more realistic event distributions |
| 3 | dbt project setup + staging models |
| 4 | dbt mart models (revenue, funnel, top products) + dbt tests (data quality) |
| 5 | Airflow DAG wiring the full pipeline end to end, scheduled |
| 6 | Streamlit dashboard on top of the marts |
| 7 | Polish, README pass, `docs/retailpulse-report.pdf`, tag `week01-complete` |

## Decisions log

- **DuckDB over Postgres**: no server process to manage for a solo daily-build project, still real SQL + dbt-compatible, upgrade path to Postgres/Snowflake later is just a dbt profile change.
- **Synthetic data over a public dataset**: full control over volume/schema/day-to-day evolution, matches the "day 2 hardens ingestion" plan without waiting on external data quirks.
- **Airflow over a lighter scheduler (e.g. Prefect)**: still the most commonly required orchestrator in job postings; worth the extra setup weight for portfolio value.
- **In-repo `dbt/profiles.yml` over `~/.dbt/profiles.yml`**: keeps the project runnable with a plain `git clone` + `dbt run --profiles-dir .`, no machine-specific setup step to document.
- **A plain singular test (`dbt/tests/assert_*.sql`) over adding `dbt_utils` for the price/quantity range check**: one query does the whole job; not worth a package dependency for a single check.
