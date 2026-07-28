"""Shared constants describing the synthetic retail event schema.

Kept separate from the generation logic so ingestion/tests can import the
same vocabulary without pulling in Faker or generation code.
"""

EVENT_TYPES = ("page_view", "add_to_cart", "purchase")

# Rough weights so purchase funnels look like a real funnel:
# lots of views, fewer add-to-carts, fewer purchases still.
EVENT_TYPE_WEIGHTS = (0.7, 0.2, 0.1)

PRODUCT_CATEGORIES = (
    "electronics",
    "home_and_kitchen",
    "apparel",
    "beauty",
    "sports_and_outdoors",
    "books",
)

REQUIRED_FIELDS = (
    "event_id",
    "event_type",
    "user_id",
    "product_id",
    "product_category",
    "timestamp",
)

# price/quantity only apply to add_to_cart and purchase events
CART_EVENT_TYPES = ("add_to_cart", "purchase")
