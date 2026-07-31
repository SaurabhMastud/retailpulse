from datetime import datetime, timedelta, timezone

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


def test_events_are_grouped_into_sessions_by_same_user():
    events = generate_events(count=300, seed=42, max_session_length=4)
    sessions: dict[str, set[str]] = {}
    for event in events:
        sessions.setdefault(event["session_id"], set()).add(event["user_id"])

    # every session belongs to exactly one user, and there's more than one
    # event per session on average (otherwise "sessions" would be pointless)
    assert all(len(users) == 1 for users in sessions.values())
    assert len(sessions) < len(events)


def test_session_events_are_capped_at_max_length():
    events = generate_events(count=100, seed=7, max_session_length=3)
    counts: dict[str, int] = {}
    for event in events:
        counts[event["session_id"]] = counts.get(event["session_id"], 0) + 1
    assert all(c <= 3 for c in counts.values())


def test_product_catalog_is_stable_across_differently_seeded_batches():
    # a product_id must carry the same category and price in every batch --
    # otherwise date-grained marts split one product into duplicate rows
    def mapping(events):
        return {e["product_id"]: e["product_category"] for e in events}

    a = mapping(generate_events(count=300, seed=1))
    b = mapping(generate_events(count=300, seed=2))
    shared = a.keys() & b.keys()
    assert shared, "batches should overlap on products"
    assert all(a[pid] == b[pid] for pid in shared)


def test_events_within_a_session_are_in_chronological_order():
    # the funnel mart attributes a session to its first event's date, so
    # per-session timestamps have to be non-decreasing in emission order
    events = generate_events(count=400, seed=11, max_session_length=4)
    last_seen: dict[str, datetime] = {}
    for event in events:
        ts = datetime.fromisoformat(event["timestamp"])
        previous = last_seen.get(event["session_id"])
        if previous is not None:
            assert ts >= previous
        last_seen[event["session_id"]] = ts


def test_events_span_multiple_days_when_days_is_set():
    events = generate_events(count=400, seed=13, days=14)
    dates = {datetime.fromisoformat(e["timestamp"]).date() for e in events}
    # 400 events uniformly spread over 14 days should touch most of them;
    # a lower bound of 5 keeps the test from being flaky on unlucky draws
    assert len(dates) >= 5


def test_events_stay_within_the_requested_day_window():
    events = generate_events(count=200, seed=17, days=3)
    now = datetime.now(timezone.utc)
    # sessions start within the window; trailing events in a session can run
    # a few minutes past `now`, so allow a small slack on the upper bound
    for event in events:
        ts = datetime.fromisoformat(event["timestamp"])
        assert now - timedelta(days=3) <= ts <= now + timedelta(minutes=10)
