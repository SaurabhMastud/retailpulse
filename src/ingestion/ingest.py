"""Loads validated raw events from a JSONL landing file into DuckDB.

Reads a JSONL landing file, validates each event, quarantines invalid ones,
and upserts the rest into `raw_events` (idempotent on `event_id`, both across
re-runs and within a single batch).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

from src.ingestion.validate import validate_batch

RAW_EVENTS_TABLE = "raw_events"
QUARANTINE_TABLE = "quarantined_events"

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {RAW_EVENTS_TABLE} (
    event_id VARCHAR PRIMARY KEY,
    event_type VARCHAR,
    user_id VARCHAR,
    session_id VARCHAR,
    product_id VARCHAR,
    product_category VARCHAR,
    price DOUBLE,
    quantity INTEGER,
    timestamp TIMESTAMP
)
"""

# Raw JSON + reason kept side by side so a bad event can be inspected and
# replayed later without needing the original source file.
CREATE_QUARANTINE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {QUARANTINE_TABLE} (
    event_id VARCHAR,
    raw_event VARCHAR,
    error VARCHAR,
    quarantined_at TIMESTAMP DEFAULT current_timestamp
)
"""


def read_jsonl(path: str | Path) -> list[dict]:
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def ingest(source_path: str | Path, warehouse_path: str | Path) -> dict:
    events = read_jsonl(source_path)
    valid, invalid = validate_batch(events)

    Path(warehouse_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(warehouse_path))
    try:
        con.execute(CREATE_TABLE_SQL)
        con.execute(CREATE_QUARANTINE_TABLE_SQL)

        loaded = 0
        duplicates = 0
        for event in valid:
            # RETURNING tells us whether the row actually landed (vs. being
            # skipped by ON CONFLICT) -- covers both re-running the same
            # source file and duplicate event_ids within one batch, since
            # DuckDB commits each statement immediately.
            returned = con.execute(
                f"""
                INSERT INTO {RAW_EVENTS_TABLE}
                    (event_id, event_type, user_id, session_id, product_id, product_category, price, quantity, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (event_id) DO NOTHING
                RETURNING event_id
                """,
                [
                    event["event_id"],
                    event["event_type"],
                    event["user_id"],
                    event["session_id"],
                    event["product_id"],
                    event["product_category"],
                    event.get("price"),
                    event.get("quantity"),
                    event["timestamp"],
                ],
            ).fetchall()
            if returned:
                loaded += 1
            else:
                duplicates += 1

        for event, error in invalid:
            con.execute(
                f"INSERT INTO {QUARANTINE_TABLE} (event_id, raw_event, error) VALUES (?, ?, ?)",
                [event.get("event_id"), json.dumps(event), error],
            )
    finally:
        con.close()

    return {
        "read": len(events),
        "loaded": loaded,
        "duplicates": duplicates,
        "rejected": len(invalid),
        "errors": invalid,
    }


def format_ingest_summary(result: dict) -> str:
    """Render an ingest() result as human-readable lines.

    Pulled out of main() so other entrypoints (the day-5 Airflow DAG, in
    particular) can log the same summary without shelling out to this CLI.
    """
    lines = [
        f"Read {result['read']} events, loaded {result['loaded']}, "
        f"duplicates {result['duplicates']}, rejected {result['rejected']}"
    ]
    for event, error in result["errors"]:
        lines.append(f"  rejected {event.get('event_id', '<unknown>')}: {error}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest raw JSONL events into the DuckDB warehouse.")
    parser.add_argument("--source", type=str, required=True, help="path to a JSONL events file")
    parser.add_argument(
        "--warehouse",
        type=str,
        default="data/warehouse/retailpulse.duckdb",
        help="path to the DuckDB warehouse file",
    )
    args = parser.parse_args()

    result = ingest(args.source, args.warehouse)
    print(format_ingest_summary(result))


if __name__ == "__main__":
    main()
