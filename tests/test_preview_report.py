import json

from src.ingestion.ingest import ingest
from src.ingestion.preview_report import build_preview_report, format_preview_report


def _write_jsonl(tmp_path, events, name="events.jsonl"):
    path = tmp_path / name
    with open(path, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
    return path


def test_build_preview_report_reflects_loaded_data(tmp_path):
    events = [
        {
            "event_id": "e1",
            "event_type": "page_view",
            "user_id": "u1",
            "session_id": "s1",
            "product_id": "p1",
            "product_category": "books",
            "timestamp": "2026-07-28T00:00:00+00:00",
        },
        {
            "event_id": "e2",
            "event_type": "purchase",
            "user_id": "u2",
            "session_id": "s2",
            "product_id": "p2",
            "product_category": "books",
            "price": 12.0,
            "quantity": 1,
            "timestamp": "2026-07-28T00:01:00+00:00",
        },
        {
            "event_id": "e3",
            "event_type": "not_a_type",  # gets quarantined
            "user_id": "u1",
            "session_id": "s1",
            "product_id": "p1",
            "product_category": "books",
            "timestamp": "2026-07-28T00:02:00+00:00",
        },
    ]
    source = _write_jsonl(tmp_path, events)
    warehouse = tmp_path / "preview.duckdb"
    ingest(source, warehouse)

    report = build_preview_report(str(warehouse))
    assert report["total_events"] == 2
    assert report["unique_users"] == 2
    assert report["unique_sessions"] == 2
    assert report["by_event_type"] == {"page_view": 1, "purchase": 1}
    assert report["top_categories"] == [("books", 2)]
    assert report["quarantined"] == 1


def test_format_preview_report_renders_readable_text():
    report = {
        "total_events": 5,
        "unique_users": 3,
        "unique_sessions": 4,
        "by_event_type": {"page_view": 3, "purchase": 2},
        "top_categories": [("books", 5)],
        "quarantined": 0,
    }
    text = format_preview_report(report)
    assert "Total events:      5" in text
    assert "page_view" in text
    assert "books" in text
