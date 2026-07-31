"""The end-to-end pipeline as four plain functions: generate -> ingest -> dbt run -> dbt test.

The Airflow DAG (`dags/`) is a thin wrapper over these, not a reimplementation.
Keeping the steps here means the whole pipeline stays runnable and testable
without an Airflow install -- which matters, since Airflow has no native
Windows support and this project is developed on Windows.

Every step returns a dict so a caller (a DAG task, the CLI below) can log or
push the result without re-parsing stdout.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.generator.event_generator import generate_events, write_jsonl
from src.ingestion.ingest import format_ingest_summary, ingest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WAREHOUSE = PROJECT_ROOT / "data" / "warehouse" / "retailpulse.duckdb"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DBT_DIR = PROJECT_ROOT / "dbt"


def generate_step(
    count: int = 1000,
    days: int = 14,
    seed: int | None = None,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    batch_id: str | None = None,
) -> dict:
    """Write one batch of synthetic events to its own landing file.

    One file per batch (named by UTC timestamp) keeps the landing zone
    immutable and append-only -- a re-run never overwrites a previous batch,
    so raw data stays replayable.
    """
    batch_id = batch_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_path = Path(raw_dir) / f"events_{batch_id}.jsonl"
    events = generate_events(count=count, seed=seed, days=days)
    write_jsonl(events, out_path)
    return {"batch_id": batch_id, "path": str(out_path), "events": len(events)}


def ingest_step(source_path: str | Path, warehouse: str | Path = DEFAULT_WAREHOUSE) -> dict:
    result = ingest(source_path, warehouse)
    return {
        "source": str(source_path),
        "read": result["read"],
        "loaded": result["loaded"],
        "duplicates": result["duplicates"],
        "rejected": result["rejected"],
        "summary": format_ingest_summary(result),
    }


def run_dbt(command: str, dbt_dir: str | Path = DBT_DIR) -> dict:
    """Run a dbt subcommand against the in-repo profile.

    Shells out rather than using dbt's programmatic runner: it's the same thing
    the DAG's operator would do, and it keeps dbt's own exit code as the single
    source of truth for pass/fail.
    """
    completed = subprocess.run(
        [sys.executable, "-m", "dbt.cli.main", command, "--profiles-dir", "."],
        cwd=str(dbt_dir),
        capture_output=True,
        text=True,
    )
    result = {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode != 0:
        raise RuntimeError(f"dbt {command} failed (exit {completed.returncode}):\n{completed.stdout}")
    return result


def run_pipeline(
    count: int = 1000,
    days: int = 14,
    seed: int | None = None,
    warehouse: str | Path = DEFAULT_WAREHOUSE,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
) -> dict:
    """Run all four steps in order. Raises on the first failure."""
    generated = generate_step(count=count, days=days, seed=seed, raw_dir=raw_dir)
    ingested = ingest_step(generated["path"], warehouse=warehouse)
    dbt_run = run_dbt("run")
    dbt_test = run_dbt("test")
    return {
        "generate": generated,
        "ingest": ingested,
        "dbt_run": dbt_run,
        "dbt_test": dbt_test,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full RetailPulse pipeline once.")
    parser.add_argument("--count", type=int, default=1000, help="events to generate")
    parser.add_argument("--days", type=int, default=14, help="spread events over the last N days")
    parser.add_argument("--seed", type=int, default=None, help="random seed")
    args = parser.parse_args()

    result = run_pipeline(count=args.count, days=args.days, seed=args.seed)
    print(f"Generated {result['generate']['events']} events -> {result['generate']['path']}")
    print(result["ingest"]["summary"])
    print("dbt run: ok")
    print("dbt test: ok")


if __name__ == "__main__":
    main()
