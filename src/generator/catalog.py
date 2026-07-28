"""A small fixed product catalog the generator draws from.

A fixed catalog (rather than fully random product ids) keeps "top products"
style analytics meaningful later in the pipeline -- there needs to be
repetition for a top-N query to say anything interesting.
"""
import random

from src.generator.schema import PRODUCT_CATEGORIES


def build_catalog(num_products: int = 60, seed: int | None = None) -> list[dict]:
    """Build a deterministic-if-seeded list of {product_id, category, price} dicts."""
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
