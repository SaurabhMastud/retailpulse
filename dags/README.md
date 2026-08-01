# Airflow DAGs

`retailpulse_pipeline.py` — one DAG, scheduled `@daily`:

```
generate_events >> ingest_events >> dbt_seed >> dbt_run >> dbt_test
```

`dbt_seed` loads the product dimension from `dbt/seeds/products.csv` before
anything refs it. `dbt_test` raises on a non-zero dbt exit, so a data quality violation in the
marts fails the run instead of passing silently downstream.

## Why the DAG is thin

Every step is a function in [`src/pipeline.py`](../src/pipeline.py). This file
is wiring and scheduling only. Two reasons:

- the pipeline stays runnable and testable without Airflow — `python -m
  src.pipeline` does the same steps
- Airflow has **no native Windows support**, and this project is developed on
  Windows. Keeping the logic out of the DAG means the Windows box can still
  exercise the whole pipeline

`ingest_events` reads the landing-file path from the `generate_events` XCom
rather than reconstructing it, so the two tasks can't drift on a filename
convention.

## Running it

The DAG is written against Airflow 2.9 (pinned in `requirements.txt`) and needs
Linux, WSL, or Docker:

```bash
export AIRFLOW_HOME=~/airflow
airflow db init
ln -s "$(pwd)/dags/retailpulse_pipeline.py" "$AIRFLOW_HOME/dags/"
airflow dags test retailpulse_pipeline
```

## Tests

`tests/test_dag.py` checks the DAG in two layers: AST-level checks on task ids,
`>>` wiring order, and that every `pipeline.*` call in the DAG still exists
(these run everywhere), plus a real `DagBag` import check that runs only where
Airflow is installed.
