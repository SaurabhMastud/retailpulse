import random

from src.generator.catalog import build_catalog
from src.generator.schema import PRODUCT_CATEGORIES
from src.generator.users import build_user_activity_weights, build_user_profiles, pick_product_for_user


def test_build_user_profiles_assigns_known_categories():
    rng = random.Random(1)
    profiles = build_user_profiles(["u1", "u2", "u3"], rng)
    assert set(profiles.keys()) == {"u1", "u2", "u3"}
    for categories in profiles.values():
        assert 1 <= len(categories) <= 2
        assert set(categories) <= set(PRODUCT_CATEGORIES)


def test_build_user_activity_weights_returns_one_weight_per_user():
    rng = random.Random(5)
    user_ids = [f"u{i}" for i in range(50)]
    weights = build_user_activity_weights(user_ids, rng)
    assert len(weights) == len(user_ids)
    assert all(w > 0 for w in weights)


def test_user_activity_weights_are_skewed_not_uniform():
    rng = random.Random(6)
    user_ids = [f"u{i}" for i in range(100)]
    weights = build_user_activity_weights(user_ids, rng)

    # A handful of "regulars" should account for a large share of total
    # weight -- this is the whole point of a Zipf-style distribution.
    total = sum(weights)
    top_10_share = sum(sorted(weights, reverse=True)[:10]) / total
    assert top_10_share > 0.3  # far more than 10/100 = 10% a uniform draw would give


def test_pick_product_for_user_stays_in_profile_when_affinity_is_forced():
    rng = random.Random(2)
    catalog = build_catalog(num_products=60, seed=2)
    profile = ["books"]

    # affinity_strength=1.0 means it should always honor the profile
    # (given the catalog has books products, which it does with 60 items).
    for _ in range(20):
        product = pick_product_for_user(rng, catalog, profile, affinity_strength=1.0)
        assert product["product_category"] == "books"


def test_pick_product_for_user_falls_back_when_no_affinity():
    rng = random.Random(3)
    catalog = build_catalog(num_products=60, seed=3)

    # affinity_strength=0.0 means it should always ignore the profile.
    picks = [pick_product_for_user(rng, catalog, ["books"], affinity_strength=0.0) for _ in range(30)]
    categories_seen = {p["product_category"] for p in picks}
    assert len(categories_seen) > 1  # not stuck on a single category


def test_affinity_skews_distribution_toward_preferred_category(monkeypatch=None):
    rng = random.Random(4)
    catalog = build_catalog(num_products=60, seed=4)
    profile = ["electronics"]

    picks = [pick_product_for_user(rng, catalog, profile, affinity_strength=0.9) for _ in range(200)]
    electronics_share = sum(1 for p in picks if p["product_category"] == "electronics") / len(picks)
    assert electronics_share > 0.5  # clearly skewed, not a uniform ~1/6 share
