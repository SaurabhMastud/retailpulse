"""The end-to-end pipeline as plain functions: generate -> ingest -> dbt seed/run -> dbt test.

The Airflow DAG (`dags/`) is a thin wrapper over these, not a reimplementation.
Keeping the steps here means the whole pipeline stays runnable and testable
without an Airflow install -- which matters, since Airflow has no native
Windows support and this project is developed on Windows.

Every step returns a dict so a caller (a DAG task, the CLI below) can log or
push the result without re-parsing stdout.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from src.generator.event_generator import generate_events, write_jsonl
from src.ingestion.ingest import format_ingest_summary, ingest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WAREHOUSE = PROJECT_ROOT / "data" / "warehouse" / "retailpulse.duckdb"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DBT_DIR = PROJECT_ROOT / "dbt"

PIPELINE_RUNS_TABLE = "pipeline_runs"

# Run metadata lives here rather than in src/ingestion: ingest() is a library
# call that loads a file, while "which batch ran, when, and how much of it was
# rejected" is an orchestration-level fact. Without it, a batch that quietly
# rejected half its rows is only visible in whatever captured the run's stdout.
CREATE_PIPELINE_RUNS_SQL = f"""
CREATE TABLE IF NOT EXISTS {PIPELINE_RUNS_TABLE} (
    batch_id VARCHAR,
    source_file VARCHAR,
    events_read INTEGER,
    events_loaded INTEGER,
    duplicates INTEGER,
    rejected INTEGER,
    ingested_at TIMESTAMP DEFAULT current_timestamp
)
"""


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


def record_run(warehouse: str | Path, batch_id: str, source_path: str | Path, result: dict) -> None:
    """Append one row to `pipeline_runs` describing an ingest."""
    con = duckdb.connect(str(warehouse))
    try:
        con.execute(CREATE_PIPELINE_RUNS_SQL)
        con.execute(
            f"""
            INSERT INTO {PIPELINE_RUNS_TABLE}
                (batch_id, source_file, events_read, events_loaded, duplicates, rejected)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                batch_id,
                str(source_path),
                result["read"],
                result["loaded"],
                result["duplicates"],
                result["rejected"],
            ],
        )
    finally:
        con.close()


def ingest_step(
    source_path: str | Path,
    warehouse: str | Path = DEFAULT_WAREHOUSE,
    batch_id: str | None = None,
) -> dict:
    result = ingest(source_path, warehouse)
    # every ingest is audited, including retries -- a batch that appears twice
    # with duplicates == read is exactly what a safe retry should look like
    record_run(warehouse, batch_id or Path(source_path).stem, source_path, result)
    return {
        "source": str(source_path),
        "batch_id": batch_id or Path(source_path).stem,
        "read": result["read"],
        "loaded": result["loaded"],
        "duplicates": result["duplicates"],
        "rejected": result["rejected"],
        "summary": format_ingest_summary(result),
    }


def run_dbt(
    command: str, dbt_dir: str | Path = DBT_DIR, warehouse: str | Path | None = None
) -> dict:
    """Run a dbt subcommand against the in-repo profile.

    Shells out rather than using dbt's programmatic runner: it's the same thing
    the DAG's operator would do, and it keeps dbt's own exit code as the single
    source of truth for pass/fail.

    `warehouse` overrides the profile's target path via RETAILPULSE_WAREHOUSE,
    so models can be built into a scratch database without editing profiles.yml.
    """
    env = None
    if warehouse is not None:
        env = {**os.environ, "RETAILPULSE_WAREHOUSE": str(Path(warehouse).resolve())}

    completed = subprocess.run(
        [sys.executable, "-m", "dbt.cli.main", command, "--profiles-dir", "."],
        cwd=str(dbt_dir),
        capture_output=True,
        text=True,
        env=env,
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


def build_models(warehouse: str | Path = DEFAULT_WAREHOUSE) -> dict:
    """Load seeds, then build models -- in that order, which is not optional.

    Marts `ref` the products seed, so `dbt run` against a warehouse that has
    never been seeded fails with "Table with name products does not exist".
    That ordering rule lived in four places and was already forgotten in one of
    them (the dashboard test fixture) the day the seed was introduced; it lives
    here now so there is one place to get it right.
    """
    return {
        "dbt_seed": run_dbt("seed", warehouse=warehouse),
        "dbt_run": run_dbt("run", warehouse=warehouse),
    }


def replay_step(
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    warehouse: str | Path = DEFAULT_WAREHOUSE,
    since: str | None = None,
) -> dict:
    """Re-ingest every landing file, oldest first.

    The landing zone is append-only -- one immutable file per batch, named
    `events_<UTC timestamp>.jsonl` -- which is what makes this possible at all:
    the warehouse can be deleted and rebuilt from raw data without regenerating
    anything. Without a replay path, "append-only landing zone" is a claim the
    project never actually cashes in.

    Files sort chronologically because the batch id is a zero-padded UTC
    timestamp, so lexicographic order is time order. Order matters only for the
    audit trail (`pipeline_runs`), not for correctness: ingestion upserts on
    event_id, so replaying is idempotent and safe to re-run over a warehouse
    that already holds some of the batches.

    `since` filters to batch ids at or after a prefix (e.g. "20260801"), for
    replaying a window rather than all of history.
    """
    files = sorted(Path(raw_dir).glob("events_*.jsonl"))
    if since is not None:
        files = [f for f in files if f.stem.removeprefix("events_") >= since]

    totals = {"files": 0, "read": 0, "loaded": 0, "duplicates": 0, "rejected": 0}
    batches = []
    for path in files:
        result = ingest_step(path, warehouse=warehouse, batch_id=path.stem.removeprefix("events_"))
        totals["files"] += 1
        for key in ("read", "loaded", "duplicates", "rejected"):
            totals[key] += result[key]
        batches.append(result)

    return {**totals, "batches": batches}


def rebuild_from_landing(
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    warehouse: str | Path = DEFAULT_WAREHOUSE,
    since: str | None = None,
) -> dict:
    """Replay the landing zone, then rebuild and test the models on top of it."""
    replayed = replay_step(raw_dir=raw_dir, warehouse=warehouse, since=since)
    return {
        "replay": replayed,
        **build_models(warehouse=warehouse),
        "dbt_test": run_dbt("test", warehouse=warehouse),
    }


def run_pipeline(
    count: int = 1000,
    days: int = 14,
    seed: int | None = None,
    warehouse: str | Path = DEFAULT_WAREHOUSE,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
) -> dict:
    """Run all four steps in order. Raises on the first failure."""
    generated = generate_step(count=count, days=days, seed=seed, raw_dir=raw_dir)
    ingested = ingest_step(generated["path"], warehouse=warehouse, batch_id=generated["batch_id"])
    built = build_models(warehouse=warehouse)
    dbt_test = run_dbt("test", warehouse=warehouse)
    return {
        "generate": generated,
        "ingest": ingested,
        **built,
        "dbt_test": dbt_test,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full RetailPulse pipeline once.")
    parser.add_argument("--count", type=int, default=1000, help="events to generate")
    parser.add_argument("--days", type=int, default=14, help="spread events over the last N days")
    parser.add_argument("--seed", type=int, default=None, help="random seed")
    parser.add_argument(
        "--replay",
        action="store_true",
        help="skip generation and rebuild the warehouse from the landing zone instead",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="with --replay, only batches with an id at or after this prefix (e.g. 20260801)",
    )
    args = parser.parse_args()

    if args.replay:
        result = rebuild_from_landing(since=args.since)
        replay = result["replay"]
        print(
            f"Replayed {replay['files']} batches: read {replay['read']}, "
            f"loaded {replay['loaded']}, duplicates {replay['duplicates']}, "
            f"rejected {replay['rejected']}"
        )
        print("dbt seed: ok")
        print("dbt run: ok")
        print("dbt test: ok")
        return

    result = run_pipeline(count=args.count, days=args.days, seed=args.seed)
    print(f"Generated {result['generate']['events']} events -> {result['generate']['path']}")
    print(result["ingest"]["summary"])
    print("dbt seed: ok")
    print("dbt run: ok")
    print("dbt test: ok")


if __name__ == "__main__":
    main()
