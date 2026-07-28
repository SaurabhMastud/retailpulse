# Airflow DAGs (lands day 5)

Will hold a single DAG (`retailpulse_pipeline`) wiring:

```
generate_events >> ingest_events >> dbt_run >> dbt_test
```

scheduled `@daily`, with `dbt_test` failing the run (not just warning) on any data quality violation in the marts.
