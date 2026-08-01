"""The product catalog and the dbt seed exported from it.

The seed is committed to the repo but generated from `build_catalog()`, so the
failure mode worth testing is drift: someone edits products.csv by hand, or
changes the catalog and forgets to re-export. Either way the dimension stops
describing the products the generator actually emits, and the relationships
test on stg_events.product_id starts failing on real data instead of here.
"""
import csv

from src.generator.catalog import CATALOG_CSV_PATH, build_catalog, write_catalog_csv


def test_catalog_is_stable_across_calls():
    assert build_catalog() == build_catalog()


def test_committed_seed_matches_the_catalog(tmp_path):
    regenerated = write_catalog_csv(tmp_path / "products.csv")
    assert regenerated.read_bytes() == CATALOG_CSV_PATH.read_bytes(), (
        "dbt/seeds/products.csv is out of date -- run `python -m src.generator.catalog`"
    )


def test_seed_covers_every_product_the_generator_can_emit():
    with CATALOG_CSV_PATH.open(encoding="utf-8", newline="") as f:
        seeded = {row["product_id"] for row in csv.DictReader(f)}
    assert {p["product_id"] for p in build_catalog()} <= seeded
