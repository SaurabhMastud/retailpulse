"""A small fixed product catalog the generator draws from.

A fixed catalog (rather than fully random product ids) keeps "top products"
style analytics meaningful later in the pipeline -- there needs to be
repetition for a top-N query to say anything interesting.

The same catalog is exported to `dbt/seeds/products.csv` so the warehouse has
a product dimension to validate events against. It is exported rather than
hand-maintained: two hand-written copies of the same reference data drift, and
the drift only shows up as events referencing products the dimension has never
heard of.
"""
import argparse
import csv
import random
from pathlib import Path

from src.generator.schema import PRODUCT_CATEGORIES

CATALOG_CSV_PATH = Path(__file__).resolve().parents[2] / "dbt" / "seeds" / "products.csv"
CATALOG_CSV_COLUMNS = ["product_id", "product_category", "price"]

# The catalog is a reference dimension, not per-batch random data: a given
# product_id has to map to the same category and price in every batch, or the
# warehouse sees one product under two categories and marts grained on
# (date, product_id) split into duplicate rows. Seeding it independently of the
# event-generation seed is what keeps that stable across runs.
CATALOG_SEED = 20260728


def build_catalog(num_products: int = 60, seed: int | None = CATALOG_SEED) -> list[dict]:
    """Build the product catalog -- stable across runs unless `seed` is overridden."""
    rng = random.Random(seed)
    catalog = []
    for i in range(num_products):
        category = rng.choice(PRODUCT_CATEGORIES)
        base_price = {
            "electronics": (25, 900),
            "home_and_kitchen": (10, 250),
            "apparel": (8, 120),
            "beauty": (5, 80),
            "sports_and_outdoors": (10, 300),
            "books": (6, 40),
        }[category]
        price = round(rng.uniform(*base_price), 2)
        catalog.append(
            {
                "product_id": f"P{i:04d}",
                "product_category": category,
                "price": price,
            }
        )
    return catalog


def write_catalog_csv(out_path: str | Path = CATALOG_CSV_PATH, num_products: int = 60) -> Path:
    """Write the catalog out as the dbt seed. Deterministic -- same bytes every run."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # newline="" is csv's documented requirement; without it Windows writes \r\r\n
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CATALOG_CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(build_catalog(num_products=num_products))
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate the dbt product seed from the catalog.")
    parser.add_argument("--out", type=str, default=str(CATALOG_CSV_PATH), help="output CSV path")
    args = parser.parse_args()
    print(f"Wrote catalog seed to {write_catalog_csv(args.out)}")


if __name__ == "__main__":
    main()
