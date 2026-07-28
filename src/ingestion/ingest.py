"""Loads validated raw events from a JSONL landing file into DuckDB.

This is deliberately the dumbest possible "ingestion" -- read file, validate
rows, append to a raw_events table. Day 2 hardens this (batching, dedup on
event_id, quarantine table for invalid rows) once there's a real pipeline
around it to harden against.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

from src.ingestion.validate import validate_batch

RAW_EVENTS_TABLE = "raw_events"

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {RAW_EVENTS_TABLE} (
    event_id VARCHAR PRIMARY KEY,
    event_type VARCHAR,
    user_id VARCHAR,
    product_id VARCHAR,
    product_category VARCHAR,
    price DOUBLE,
    quantity INTEGER,
    timestamp TIMESTAMP
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
        loaded = 0
        for event in valid:
            con.execute(
                f"""
                INSERT INTO {RAW_EVENTS_TABLE}
                    (event_id, event_type, user_id, product_id, product_category, price, quantity, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (event_id) DO NOTHING
                """,
                [
                    event["event_id"],
                    event["event_type"],
                    event["user_id"],
                    event["product_id"],
                    event["product_category"],
                    event.get("price"),
                    event.get("quantity"),
                    event["timestamp"],
                ],
            )
            loaded += 1
    finally:
        con.close()

    return {"read": len(events), "loaded": loaded, "rejected": len(invalid), "errors": invalid}


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
    print(f"Read {result['read']} events, loaded {result['loaded']}, rejected {result['rejected']}")
    for event, error in result["errors"]:
        print(f"  rejected {event.get('event_id', '<unknown>')}: {error}")


if __name__ == "__main__":
    main()
