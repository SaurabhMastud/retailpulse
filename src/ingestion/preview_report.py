"""A quick read-only preview of what's in the warehouse.

dbt marts don't land until day 3-4, but there's no reason to fly blind on
whether the generator + ingestion pipeline is actually producing sane data
in the meantime -- this is a thin, temporary stand-in for the eventual
Streamlit dashboard, not a permanent part of the architecture.
"""
from __future__ import annotations

import argparse

import duckdb

from src.ingestion.ingest import RAW_EVENTS_TABLE, QUARANTINE_TABLE


def build_preview_report(warehouse_path: str) -> dict:
    con = duckdb.connect(warehouse_path, read_only=True)
    try:
        total_events = con.execute(f"SELECT COUNT(*) FROM {RAW_EVENTS_TABLE}").fetchone()[0]
        unique_users = con.execute(f"SELECT COUNT(DISTINCT user_id) FROM {RAW_EVENTS_TABLE}").fetchone()[0]
        unique_sessions = con.execute(
            f"SELECT COUNT(DISTINCT session_id) FROM {RAW_EVENTS_TABLE}"
        ).fetchone()[0]
        by_event_type = dict(
            con.execute(
                f"SELECT event_type, COUNT(*) FROM {RAW_EVENTS_TABLE} GROUP BY 1 ORDER BY 2 DESC"
            ).fetchall()
        )
        top_categories = con.execute(
            f"""
            SELECT product_category, COUNT(*) AS n
            FROM {RAW_EVENTS_TABLE}
            GROUP BY 1
            ORDER BY n DESC
            LIMIT 5
            """
        ).fetchall()
        quarantined = con.execute(f"SELECT COUNT(*) FROM {QUARANTINE_TABLE}").fetchone()[0]
    finally:
        con.close()

    return {
        "total_events": total_events,
        "unique_users": unique_users,
        "unique_sessions": unique_sessions,
        "by_event_type": by_event_type,
        "top_categories": top_categories,
        "quarantined": quarantined,
    }


def format_preview_report(report: dict) -> str:
    lines = [
        f"Total events:      {report['total_events']}",
        f"Unique users:      {report['unique_users']}",
        f"Unique sessions:   {report['unique_sessions']}",
        f"Quarantined rows:  {report['quarantined']}",
        "By event type:",
    ]
    for event_type, count in report["by_event_type"].items():
        lines.append(f"  {event_type:<12} {count}")
    lines.append("Top categories:")
    for category, count in report["top_categories"]:
        lines.append(f"  {category:<20} {count}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview basic stats from the RetailPulse warehouse.")
    parser.add_argument(
        "--warehouse",
        type=str,
        default="data/warehouse/retailpulse.duckdb",
        help="path to the DuckDB warehouse file",
    )
    args = parser.parse_args()

    report = build_preview_report(args.warehouse)
    print(format_preview_report(report))


if __name__ == "__main__":
    main()
