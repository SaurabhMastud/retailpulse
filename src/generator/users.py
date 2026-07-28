"""User profile modeling for the event generator.

Real shoppers aren't uniformly random across categories -- someone browsing
electronics tends to keep browsing electronics. Giving each synthetic user a
small set of preferred categories makes "top category per user" / affinity
style analytics on the eventual marts mean something, instead of every
category looking flat by construction.
"""
from __future__ import annotations

import random

from src.generator.schema import PRODUCT_CATEGORIES


def build_user_profiles(
    user_ids: list[str],
    rng: random.Random,
    max_preferred_categories: int = 2,
) -> dict[str, list[str]]:
    """Assign each user 1-2 preferred categories drawn from PRODUCT_CATEGORIES."""
    profiles = {}
    for user_id in user_ids:
        k = rng.randint(1, max_preferred_categories)
        profiles[user_id] = rng.sample(PRODUCT_CATEGORIES, k=k)
    return profiles


def build_user_activity_weights(user_ids: list[str], rng: random.Random) -> list[float]:
    """Give each user a Zipf-like activity weight so a minority of "regulars"
    account for a disproportionate share of events, instead of every user
    being equally likely to show up -- matches real traffic much better than
    a uniform pick and gives later "top users" / retention analysis something
    to actually find.
    """
    # Zipf-style: rank users 1..N, weight ~ 1/rank, then shuffle which user
    # gets which rank so it's not correlated with user_id order.
    ranks = list(range(1, len(user_ids) + 1))
    rng.shuffle(ranks)
    return [1.0 / rank for rank in ranks]


def pick_product_for_user(
    rng: random.Random,
    catalog: list[dict],
    user_profile: list[str],
    affinity_strength: float = 0.7,
) -> dict:
    """Pick a product, biased toward the user's preferred categories.

    `affinity_strength` fraction of the time, pick from the user's preferred
    categories (falling back to the full catalog if none match); the rest of
    the time, pick from the full catalog so users still browse outside their
    usual categories sometimes.
    """
    if rng.random() < affinity_strength:
        preferred = [p for p in catalog if p["product_category"] in user_profile]
        if preferred:
            return rng.choice(preferred)
    return rng.choice(catalog)
