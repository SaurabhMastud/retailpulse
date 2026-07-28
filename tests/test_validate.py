import pytest

from src.ingestion.validate import InvalidEventError, validate_batch, validate_event

VALID_PAGE_VIEW = {
    "event_id": "e1",
    "event_type": "page_view",
    "user_id": "u1",
    "product_id": "p1",
    "product_category": "books",
    "timestamp": "2026-07-28T00:00:00+00:00",
}

VALID_PURCHASE = {
    **VALID_PAGE_VIEW,
    "event_id": "e2",
    "event_type": "purchase",
    "price": 19.99,
    "quantity": 2,
}


def test_valid_page_view_passes():
    validate_event(VALID_PAGE_VIEW)  # should not raise


def test_valid_purchase_passes():
    validate_event(VALID_PURCHASE)  # should not raise


def test_missing_required_field_rejected():
    bad = {k: v for k, v in VALID_PAGE_VIEW.items() if k != "user_id"}
    with pytest.raises(InvalidEventError):
        validate_event(bad)


def test_unknown_event_type_rejected():
    bad = {**VALID_PAGE_VIEW, "event_type": "refund"}
    with pytest.raises(InvalidEventError):
        validate_event(bad)


def test_purchase_without_price_rejected():
    bad = {k: v for k, v in VALID_PURCHASE.items() if k != "price"}
    with pytest.raises(InvalidEventError):
        validate_event(bad)


def test_negative_price_rejected():
    bad = {**VALID_PURCHASE, "price": -5}
    with pytest.raises(InvalidEventError):
        validate_event(bad)


def test_zero_quantity_rejected():
    bad = {**VALID_PURCHASE, "quantity": 0}
    with pytest.raises(InvalidEventError):
        validate_event(bad)


def test_validate_batch_splits_valid_and_invalid():
    bad = {**VALID_PAGE_VIEW, "event_id": "e3", "event_type": "not_a_real_type"}
    valid, invalid = validate_batch([VALID_PAGE_VIEW, VALID_PURCHASE, bad])
    assert len(valid) == 2
    assert len(invalid) == 1
    assert invalid[0][0]["event_id"] == "e3"
