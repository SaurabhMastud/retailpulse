import json

from src.ingestion.ingest import RAW_EVENTS_TABLE, format_ingest_summary, ingest


def _write_jsonl(tmp_path, events, name="events.jsonl"):
    path = tmp_path / name
    with open(path, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
    return path


def test_ingest_loads_valid_events(tmp_path):
    import duckdb

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
            "product_category": "beauty",
            "price": 9.99,
            "quantity": 1,
            "timestamp": "2026-07-28T00:01:00+00:00",
        },
    ]
    source = _write_jsonl(tmp_path, events)
    warehouse = tmp_path / "test.duckdb"

    result = ingest(source, warehouse)
    assert result == {"read": 2, "loaded": 2, "duplicates": 0, "rejected": 0, "errors": []}

    con = duckdb.connect(str(warehouse))
    count = con.execute(f"SELECT COUNT(*) FROM {RAW_EVENTS_TABLE}").fetchone()[0]
    con.close()
    assert count == 2


def test_ingest_rejects_invalid_and_loads_rest(tmp_path):
    events = [
        {
            "event_id": "good",
            "event_type": "page_view",
            "user_id": "u1",
            "session_id": "s1",
            "product_id": "p1",
            "product_category": "books",
            "timestamp": "2026-07-28T00:00:00+00:00",
        },
        {
            "event_id": "bad",
            "event_type": "not_a_type",
            "user_id": "u1",
            "session_id": "s1",
            "product_id": "p1",
            "product_category": "books",
            "timestamp": "2026-07-28T00:00:00+00:00",
        },
    ]
    source = _write_jsonl(tmp_path, events)
    warehouse = tmp_path / "test2.duckdb"

    result = ingest(source, warehouse)
    assert result["loaded"] == 1
    assert result["rejected"] == 1


def test_ingest_is_idempotent_on_rerun(tmp_path):
    events = [
        {
            "event_id": "dup1",
            "event_type": "page_view",
            "user_id": "u1",
            "session_id": "s1",
            "product_id": "p1",
            "product_category": "books",
            "timestamp": "2026-07-28T00:00:00+00:00",
        }
    ]
    source = _write_jsonl(tmp_path, events)
    warehouse = tmp_path / "test3.duckdb"

    ingest(source, warehouse)
    result = ingest(source, warehouse)  # re-run same file

    import duckdb

    con = duckdb.connect(str(warehouse))
    count = con.execute(f"SELECT COUNT(*) FROM {RAW_EVENTS_TABLE}").fetchone()[0]
    con.close()
    assert count == 1  # no duplicate row from the second ingest run
    assert result["loaded"] == 0
    assert result["duplicates"] == 1


def test_ingest_dedupes_repeated_event_id_within_same_batch(tmp_path):
    # Same event_id twice in one source file -- should land once, not error.
    events = [
        {
            "event_id": "same-id",
            "event_type": "page_view",
            "user_id": "u1",
            "session_id": "s1",
            "product_id": "p1",
            "product_category": "books",
            "timestamp": "2026-07-28T00:00:00+00:00",
        },
        {
            "event_id": "same-id",
            "event_type": "page_view",
            "user_id": "u1",
            "session_id": "s1",
            "product_id": "p1",
            "product_category": "books",
            "timestamp": "2026-07-28T00:00:05+00:00",
        },
    ]
    source = _write_jsonl(tmp_path, events)
    warehouse = tmp_path / "test4.duckdb"

    result = ingest(source, warehouse)

    import duckdb

    con = duckdb.connect(str(warehouse))
    count = con.execute(f"SELECT COUNT(*) FROM {RAW_EVENTS_TABLE}").fetchone()[0]
    con.close()
    assert count == 1
    assert result["loaded"] == 1
    assert result["duplicates"] == 1


def test_format_ingest_summary_includes_counts_and_rejections():
    result = {
        "read": 3,
        "loaded": 1,
        "duplicates": 1,
        "rejected": 1,
        "errors": [({"event_id": "bad1"}, "unknown event_type: 'refund'")],
    }
    summary = format_ingest_summary(result)
    assert "Read 3 events" in summary
    assert "loaded 1" in summary
    assert "duplicates 1" in summary
    assert "rejected 1" in summary
    assert "bad1" in summary
    assert "unknown event_type" in summary


def test_format_ingest_summary_handles_no_errors():
    result = {"read": 2, "loaded": 2, "duplicates": 0, "rejected": 0, "errors": []}
    summary = format_ingest_summary(result)
    assert summary == "Read 2 events, loaded 2, duplicates 0, rejected 0"
