import json

from src.ingestion.ingest import RAW_EVENTS_TABLE, ingest


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
            "product_id": "p1",
            "product_category": "books",
            "timestamp": "2026-07-28T00:00:00+00:00",
        },
        {
            "event_id": "e2",
            "event_type": "purchase",
            "user_id": "u2",
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
    assert result == {"read": 2, "loaded": 2, "rejected": 0, "errors": []}

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
            "product_id": "p1",
            "product_category": "books",
            "timestamp": "2026-07-28T00:00:00+00:00",
        },
        {
            "event_id": "bad",
            "event_type": "not_a_type",
            "user_id": "u1",
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
