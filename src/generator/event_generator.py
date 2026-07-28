"""Synthetic retail event generator.

Produces JSON-lines events (page_view / add_to_cart / purchase) that stand
in for a real event stream (Kafka, Segment, etc.) for the rest of the
pipeline to consume.
"""
from __future__ import annotations

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.generator.catalog import build_catalog
from src.generator.schema import CART_EVENT_TYPES, EVENT_TYPE_WEIGHTS, EVENT_TYPES
from src.generator.users import build_user_profiles, pick_product_for_user


def _random_timestamp(rng: random.Random, window_minutes: int = 60) -> str:
    now = datetime.now(timezone.utc)
    offset = timedelta(seconds=rng.uniform(0, window_minutes * 60))
    return (now - offset).isoformat()


def generate_events(
    count: int,
    num_users: int = 200,
    num_products: int = 60,
    seed: int | None = None,
) -> list[dict]:
    """Generate `count` synthetic events as a list of dicts."""
    rng = random.Random(seed)
    catalog = build_catalog(num_products=num_products, seed=seed)
    user_ids = [f"U{i:05d}" for i in range(num_users)]
    user_profiles = build_user_profiles(user_ids, rng)

    events = []
    for _ in range(count):
        event_type = rng.choices(EVENT_TYPES, weights=EVENT_TYPE_WEIGHTS, k=1)[0]
        user_id = rng.choice(user_ids)
        product = pick_product_for_user(rng, catalog, user_profiles[user_id])
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "user_id": user_id,
            "product_id": product["product_id"],
            "product_category": product["product_category"],
            "timestamp": _random_timestamp(rng),
        }
        if event_type in CART_EVENT_TYPES:
            event["price"] = product["price"]
            event["quantity"] = rng.randint(1, 3)
        events.append(event)
    return events


def write_jsonl(events: list[dict], out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic RetailPulse events.")
    parser.add_argument("--count", type=int, default=500, help="number of events to generate")
    parser.add_argument("--out", type=str, default="data/raw/events.jsonl", help="output JSONL path")
    parser.add_argument("--seed", type=int, default=None, help="random seed for reproducibility")
    args = parser.parse_args()

    events = generate_events(count=args.count, seed=args.seed)
    write_jsonl(events, args.out)
    print(f"Wrote {len(events)} events to {args.out}")


if __name__ == "__main__":
    main()
