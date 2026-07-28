"""Raw event validation before landing rows into the warehouse.

Deliberately strict: a malformed event should be rejected here, not
discovered three layers deep in a dbt model.
"""
from __future__ import annotations

from src.generator.schema import CART_EVENT_TYPES, EVENT_TYPES, REQUIRED_FIELDS


class InvalidEventError(ValueError):
    pass


def validate_event(event: dict) -> None:
    missing = [f for f in REQUIRED_FIELDS if f not in event]
    if missing:
        raise InvalidEventError(f"event {event.get('event_id', '<unknown>')} missing fields: {missing}")

    if event["event_type"] not in EVENT_TYPES:
        raise InvalidEventError(f"unknown event_type: {event['event_type']!r}")

    if event["event_type"] in CART_EVENT_TYPES:
        if "price" not in event or "quantity" not in event:
            raise InvalidEventError(
                f"event {event['event_id']} is {event['event_type']} but missing price/quantity"
            )
        if event["price"] < 0:
            raise InvalidEventError(f"event {event['event_id']} has negative price")
        if event["quantity"] <= 0:
            raise InvalidEventError(f"event {event['event_id']} has non-positive quantity")


def validate_batch(events: list[dict]) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Split a batch into (valid_events, [(event, error_message), ...])."""
    valid, invalid = [], []
    for event in events:
        try:
            validate_event(event)
        except InvalidEventError as exc:
            invalid.append((event, str(exc)))
        else:
            valid.append(event)
    return valid, invalid
