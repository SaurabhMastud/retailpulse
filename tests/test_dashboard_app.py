"""Smoke test for the Streamlit app itself.

dashboard/queries.py is covered separately; this only checks that app.py
actually renders end to end against the project warehouse -- the failure mode
being a layout call that raises (a bad column name, a division by zero in a
metric) which no query-level test would catch.

Uses streamlit's own AppTest runner, so no browser and no new dependency.
"""
import pytest

from dashboard import queries

APP = "dashboard/app.py"


@pytest.fixture(scope="module")
def rendered():
    pytest.importorskip("streamlit.testing.v1")
    if not queries.DEFAULT_WAREHOUSE.exists():
        pytest.skip("no project warehouse built; run `python -m src.pipeline` first")

    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(APP, default_timeout=120).run()


def test_app_renders_without_raising(rendered):
    assert not rendered.exception, [e.value for e in rendered.exception]


def test_app_shows_the_headline_metrics(rendered):
    labels = [m.label for m in rendered.metric]
    assert labels == ["Gross revenue", "Purchases", "Sessions", "Session → purchase"]
    # the warehouse has data, so no metric should fall back to the em-dash
    assert all(m.value != "—" for m in rendered.metric)


def test_app_does_not_show_the_empty_warehouse_error(rendered):
    assert not rendered.error, [e.value for e in rendered.error]
