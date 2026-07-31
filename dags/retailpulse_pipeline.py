"""Airflow DAG: generate -> ingest -> dbt run -> dbt test, daily.

Deliberately thin. Every step is a function in `src/pipeline.py`, which is
where the logic and its tests live -- this file is wiring and scheduling only.
That split also keeps the pipeline runnable on machines without Airflow
(`python -m src.pipeline`), which includes the Windows box this is developed
on, since Airflow has no native Windows support.

XComs carry each step's result dict forward, so `ingest_events` reads the
landing path that `generate_events` actually wrote instead of both sides
guessing at the same filename convention.
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

# The DAG file is loaded from Airflow's dags folder, so the project root isn't
# necessarily on sys.path -- put it there before importing the pipeline.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import pipeline  # noqa: E402

DEFAULT_ARGS = {
    "owner": "retailpulse",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    # Ingestion is idempotent (upsert on event_id) and dbt models are rebuilt
    # in full, so a retry re-runs a step safely rather than double-counting.
    "depends_on_past": False,
}


def _generate(**context) -> dict:
    return pipeline.generate_step(
        count=1000,
        days=14,
        batch_id=context["ds_nodash"],
    )


def _ingest(**context) -> dict:
    generated = context["ti"].xcom_pull(task_ids="generate_events")
    result = pipeline.ingest_step(generated["path"], batch_id=generated["batch_id"])
    print(result["summary"])
    return result


def _dbt_run(**_) -> None:
    pipeline.run_dbt("run")


def _dbt_test(**_) -> None:
    # raises on non-zero exit, so a data quality violation fails the DAG run
    # rather than passing silently downstream
    pipeline.run_dbt("test")


with DAG(
    dag_id="retailpulse_pipeline",
    description="Generate synthetic retail events, ingest to DuckDB, build and test dbt models.",
    default_args=DEFAULT_ARGS,
    start_date=days_ago(1),
    schedule_interval="@daily",
    catchup=False,
    max_active_runs=1,  # one writer at a time -- DuckDB is a single-file warehouse
    tags=["retailpulse", "elt"],
) as dag:
    generate_events = PythonOperator(
        task_id="generate_events",
        python_callable=_generate,
    )
    ingest_events = PythonOperator(
        task_id="ingest_events",
        python_callable=_ingest,
    )
    dbt_run = PythonOperator(
        task_id="dbt_run",
        python_callable=_dbt_run,
    )
    dbt_test = PythonOperator(
        task_id="dbt_test",
        python_callable=_dbt_test,
    )

    generate_events >> ingest_events >> dbt_run >> dbt_test
