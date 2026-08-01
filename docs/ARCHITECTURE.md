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
event_generator.py --> data/raw/events_<batch>.jsonl --> ingest.py --> retailpulse.duckdb
                       (append-only, one file per batch)                 |
                                                                         |--> raw_events
                                                                         |--> quarantined_events  (failed validation)
                                                                         |--> pipeline_runs       (row counts per batch)
                                                                                    |
                                                          dbt staging models (typed views)
                                                                                    |
                                                          dbt marts (daily_revenue, funnel_conversion, top_products)
                                                                                    |
                                                          Streamlit dashboard
```

`src/pipeline.py` holds all four steps as functions; the Airflow DAG and the
CLI are both thin callers of it.

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

Events are generated in sessions (1-4 events, same user, clustered timestamps) rather than as independent draws -- `session_id` is what lets `funnel_conversion` group page_view → add_to_cart → purchase per visit instead of per random event. Session starts are spread over a `--days` window (default 14) so the date-grained marts have more than one date to group by.

## Day-by-day plan

| Day | Planned | What actually happened |
|---|---|---|
| 1 | Scaffolding, architecture doc, event generator, raw ingestion into DuckDB, tests | as planned |
| 2 | Ingestion hardening (schema validation, batching), more realistic event distributions | as planned, plus session grouping |
| 3 | dbt project setup + staging models | staging **and** all three marts — the staging layer left budget to pull day 4 forward |
| 4 | dbt marts + data quality tests | marts re-grained to daily, pipeline module, Airflow DAG (day 5), dashboard (day 6), run auditing |
| 5 | Airflow DAG wiring the full pipeline end to end, scheduled | done day 4 |
| 6 | Streamlit dashboard on top of the marts | done day 4 |
| 7 | Polish, README pass, `docs/retailpulse-report.pdf`, tag `week01-complete` | — |

Days 5 and 6 landed early, so days 5-6 are now open for depth rather than
breadth: incremental dbt models, a `dim_products` dimension so category lives
in one place instead of riding along on every event, backfill/replay from the
landing zone, and freshness/volume tests on the marts.

## Decisions log

- **DuckDB over Postgres**: no server process to manage for a solo daily-build project, still real SQL + dbt-compatible, upgrade path to Postgres/Snowflake later is just a dbt profile change.
- **Synthetic data over a public dataset**: full control over volume/schema/day-to-day evolution, matches the "day 2 hardens ingestion" plan without waiting on external data quirks.
- **Airflow over a lighter scheduler (e.g. Prefect)**: still the most commonly required orchestrator in job postings; worth the extra setup weight for portfolio value.
- **In-repo `dbt/profiles.yml` over `~/.dbt/profiles.yml`**: keeps the project runnable with a plain `git clone` + `dbt run --profiles-dir .`, no machine-specific setup step to document.
- **A plain singular test (`dbt/tests/assert_*.sql`) over adding `dbt_utils` for the price/quantity range check**: one query does the whole job; not worth a package dependency for a single check.
- **Marts at daily grain, not all-time** (day 4): `funnel_conversion` and `top_products` both started as single-row/all-time tables, which can only answer one question and hide every trend they exist to show. At `(date, ...)` grain any window rolls up downstream from the same table. The cost is that dbt's built-in `unique` test can't express a composite key, so the grain gets a singular test instead — still cheaper than a `dbt_utils` dependency.
- **A session is attributed to the date of its first event**: a visit crossing midnight is counted once, on the day it began. Splitting it across both dates would double-count the session and make the funnel's denominators disagree with the raw session count.
- **The product catalog is seeded independently of event generation** (`catalog.CATALOG_SEED`): it's a reference dimension, not per-batch random data. Seeding it with the run seed meant every batch invented its own `product_id -> category` mapping, and the date-grained `top_products` split one product into duplicate rows. Caught by `assert_top_products_grain_is_unique` on the first real multi-batch run — the test earned its keep immediately.
- **Pipeline logic in `src/pipeline.py`, not in the DAG**: Airflow has no native Windows support and this project is developed on Windows, so a DAG holding the logic would be untestable and unrunnable here. The DAG is wiring; the steps are plain functions with their own tests, and `python -m src.pipeline` runs the same path without an orchestrator.
- **Run auditing in `pipeline_runs` rather than in `ingest()`**: `ingest()` loads a file; "which batch ran, when, and how much it rejected" is an orchestration-level fact. Without the table, a batch that quietly rejected half its rows vanished with the run's stdout.
- **`batch_id` in `pipeline_runs` is not unique**: an idempotent retry is *supposed* to show up as a second row with `duplicates == events_read`. Making it unique would hide exactly the thing the table is for.
- **Dashboard split into `app.py` (layout) and `queries.py` (reads)**: Streamlit rendering is awkward to test, SQL isn't. The logic that can actually be wrong — window arithmetic, rate derivation, roll-ups — gets real tests against a built scratch warehouse; `app.py` gets a render smoke test through Streamlit's own `AppTest`.
- **Dashboard windows anchor on the newest date in the data, not on today**: generated batches routinely end a day or two short, and a today-anchored window renders an empty chart.
- **`profiles.yml` reads `RETAILPULSE_WAREHOUSE` with the old path as default**: lets tests and throwaway backfills build models into a scratch database without editing the profile or duplicating it.
- **The product dimension is a dbt seed exported from the Python catalog, not a model derived from events** (day 5): a `select distinct product_id, product_category from stg_events` would be a dimension that agrees with the events by construction — it can't catch anything. Exporting `build_catalog()` to `dbt/seeds/products.csv` gives the warehouse an *independent* reference, so `relationships` on `stg_events.product_id` fails when an event names a product the catalog has never heard of. Hand-maintaining the CSV was the other option and was rejected: two copies of the same reference data drift silently.
- **`dbt seed` is its own pipeline step and its own DAG task**, between ingest and `dbt run`: models and tests `ref` the seed, so it has to be loaded first, and folding it into `_dbt_run` would hide a step that can fail on its own.
- **`tests/test_catalog.py` asserts the committed CSV byte-matches a fresh export**: the seed is generated but checked in, so the realistic failure is someone editing it by hand or changing the catalog without re-exporting. Catching that in pytest beats discovering it as a `relationships` failure on production-shaped data.
