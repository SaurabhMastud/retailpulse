from src.generator.event_generator import generate_events
from src.generator.schema import EVENT_TYPES, REQUIRED_FIELDS


def test_generate_events_returns_requested_count():
    events = generate_events(count=25, seed=1)
    assert len(events) == 25


def test_generated_events_have_required_fields():
    events = generate_events(count=10, seed=2)
    for event in events:
        for field in REQUIRED_FIELDS:
            assert field in event


def test_generated_events_use_known_event_types():
    events = generate_events(count=100, seed=3)
    assert {e["event_type"] for e in events} <= set(EVENT_TYPES)


def test_cart_and_purchase_events_have_price_and_quantity():
    events = generate_events(count=200, seed=4)
    for event in events:
        if event["event_type"] in ("add_to_cart", "purchase"):
            assert "price" in event and event["price"] >= 0
            assert "quantity" in event and event["quantity"] > 0


def test_same_seed_is_deterministic():
    # event_id (uuid4) and timestamp (wall-clock relative) are intentionally
    # not seeded, so determinism is checked on the fields that are:
    # which user/product/event_type gets picked, in order.
    a = generate_events(count=30, seed=99)
    b = generate_events(count=30, seed=99)
    key = lambda events: [(e["user_id"], e["product_id"], e["event_type"]) for e in events]
    assert key(a) == key(b)
