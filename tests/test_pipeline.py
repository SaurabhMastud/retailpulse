"""Covers the pipeline steps without paying for a full dbt build.

The dbt steps are exercised separately (tests/test_dbt_project.py parses the
project; a real `dbt build` runs in the session workflow), so here `run_dbt` is
tested for its contract -- surfacing a non-zero exit as an exception -- rather
than by shelling out to dbt on every test run.
"""
import duckdb
import pytest

from src import pipeline


def test_generate_step_writes_a_batch_file(tmp_path):
    result = pipeline.generate_step(count=20, days=5, seed=1, raw_dir=tmp_path)
    written = tmp_path / f"events_{result['batch_id']}.jsonl"
    assert written.exists()
    assert result["events"] == 20
    assert len(written.read_text(encoding="utf-8").strip().splitlines()) == 20


def test_generate_step_does_not_overwrite_previous_batches(tmp_path):
    # the landing zone is append-only: two batches, two files
    first = pipeline.generate_step(count=5, seed=1, raw_dir=tmp_path, batch_id="batch_a")
    second = pipeline.generate_step(count=5, seed=1, raw_dir=tmp_path, batch_id="batch_b")
    assert first["path"] != second["path"]
    assert len(list(tmp_path.glob("*.jsonl"))) == 2


def test_ingest_step_loads_generated_events_into_the_warehouse(tmp_path):
    warehouse = tmp_path / "test.duckdb"
    generated = pipeline.generate_step(count=30, days=3, seed=2, raw_dir=tmp_path)
    result = pipeline.ingest_step(generated["path"], warehouse=warehouse)

    assert result["read"] == 30
    assert result["loaded"] == 30
    assert result["rejected"] == 0

    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        assert con.execute("select count(*) from raw_events").fetchone()[0] == 30
    finally:
        con.close()


def test_ingest_step_is_idempotent_on_the_same_batch(tmp_path):
    warehouse = tmp_path / "test.duckdb"
    generated = pipeline.generate_step(count=15, seed=3, raw_dir=tmp_path)
    pipeline.ingest_step(generated["path"], warehouse=warehouse)
    second = pipeline.ingest_step(generated["path"], warehouse=warehouse)

    assert second["loaded"] == 0
    assert second["duplicates"] == 15


def test_ingest_step_records_a_pipeline_run_row(tmp_path):
    warehouse = tmp_path / "test.duckdb"
    generated = pipeline.generate_step(count=25, seed=5, raw_dir=tmp_path, batch_id="b1")
    pipeline.ingest_step(generated["path"], warehouse=warehouse, batch_id="b1")

    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        row = con.execute(
            "select batch_id, events_read, events_loaded, rejected from pipeline_runs"
        ).fetchall()
    finally:
        con.close()

    assert row == [("b1", 25, 25, 0)]


def test_retried_ingest_is_audited_as_a_second_all_duplicate_run(tmp_path):
    # a safe retry should be visible as such, not hidden
    warehouse = tmp_path / "test.duckdb"
    generated = pipeline.generate_step(count=10, seed=6, raw_dir=tmp_path, batch_id="b2")
    pipeline.ingest_step(generated["path"], warehouse=warehouse, batch_id="b2")
    pipeline.ingest_step(generated["path"], warehouse=warehouse, batch_id="b2")

    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        runs = con.execute(
            "select events_loaded, duplicates from pipeline_runs order by ingested_at, events_loaded desc"
        ).fetchall()
    finally:
        con.close()

    assert runs == [(10, 0), (0, 10)]


def test_run_dbt_raises_on_a_failing_command(tmp_path):
    # a directory with no dbt project in it -- dbt exits non-zero
    with pytest.raises(RuntimeError, match="dbt parse failed"):
        pipeline.run_dbt("parse", dbt_dir=tmp_path)


def _landing_zone(tmp_path, batches: list[str]):
    """Write one landing file per batch id, oldest id first."""
    raw_dir = tmp_path / "raw"
    for i, batch_id in enumerate(batches):
        pipeline.generate_step(count=10, days=5, seed=100 + i, raw_dir=raw_dir, batch_id=batch_id)
    return raw_dir


def test_replay_ingests_every_landing_file(tmp_path):
    raw_dir = _landing_zone(tmp_path, ["20260801T000000", "20260801T010000", "20260802T000000"])
    warehouse = tmp_path / "replay.duckdb"

    result = pipeline.replay_step(raw_dir=raw_dir, warehouse=warehouse)

    assert result["files"] == 3
    assert result["read"] == 30
    assert result["loaded"] == 30
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        assert con.execute("select count(*) from raw_events").fetchone()[0] == 30
    finally:
        con.close()


def test_replay_processes_batches_oldest_first(tmp_path):
    # batch ids are zero-padded UTC timestamps, so lexicographic order is time
    # order -- the audit trail is only readable if replay preserves it
    raw_dir = _landing_zone(tmp_path, ["20260802T000000", "20260801T000000", "20260801T010000"])
    warehouse = tmp_path / "replay.duckdb"

    result = pipeline.replay_step(raw_dir=raw_dir, warehouse=warehouse)

    assert [b["batch_id"] for b in result["batches"]] == [
        "20260801T000000",
        "20260801T010000",
        "20260802T000000",
    ]


def test_replay_is_idempotent(tmp_path):
    # the whole point of an append-only landing zone: replaying over a warehouse
    # that already holds the batches changes nothing
    raw_dir = _landing_zone(tmp_path, ["20260801T000000", "20260801T010000"])
    warehouse = tmp_path / "replay.duckdb"

    pipeline.replay_step(raw_dir=raw_dir, warehouse=warehouse)
    second = pipeline.replay_step(raw_dir=raw_dir, warehouse=warehouse)

    assert second["loaded"] == 0
    assert second["duplicates"] == second["read"] == 20


def test_replay_rebuilds_a_deleted_warehouse_to_the_same_state(tmp_path):
    raw_dir = _landing_zone(tmp_path, ["20260801T000000", "20260801T010000", "20260802T000000"])
    warehouse = tmp_path / "replay.duckdb"

    pipeline.replay_step(raw_dir=raw_dir, warehouse=warehouse)
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        before = con.execute("select event_id from raw_events order by event_id").fetchall()
    finally:
        con.close()

    warehouse.unlink()
    pipeline.replay_step(raw_dir=raw_dir, warehouse=warehouse)
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        after = con.execute("select event_id from raw_events order by event_id").fetchall()
    finally:
        con.close()

    assert before == after


def test_replay_since_filters_to_later_batches(tmp_path):
    raw_dir = _landing_zone(tmp_path, ["20260801T000000", "20260802T000000", "20260803T000000"])
    warehouse = tmp_path / "replay.duckdb"

    result = pipeline.replay_step(raw_dir=raw_dir, warehouse=warehouse, since="20260802")

    assert result["files"] == 2
    assert [b["batch_id"] for b in result["batches"]] == ["20260802T000000", "20260803T000000"]


def test_replay_audits_one_run_per_batch(tmp_path):
    raw_dir = _landing_zone(tmp_path, ["20260801T000000", "20260801T010000"])
    warehouse = tmp_path / "replay.duckdb"

    pipeline.replay_step(raw_dir=raw_dir, warehouse=warehouse)

    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        runs = con.execute("select batch_id from pipeline_runs order by batch_id").fetchall()
    finally:
        con.close()

    assert runs == [("20260801T000000",), ("20260801T010000",)]


def test_replay_on_an_empty_landing_zone_is_a_no_op(tmp_path):
    result = pipeline.replay_step(raw_dir=tmp_path / "empty", warehouse=tmp_path / "w.duckdb")
    assert result["files"] == 0
    assert result["read"] == 0
