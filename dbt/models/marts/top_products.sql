-- Product performance at a daily grain: one row per (event_date, product_id).
-- Kept at the finest useful grain rather than all-time, so a consumer can roll
-- up any window it wants (last 7 days, month to date) from the same table --
-- an all-time table can only answer one question.
--
-- product_category comes from the products dimension, not from the copy the
-- event happened to carry. An event is a claim about what a product is; the
-- catalog is the record. If every event for a product named the wrong category,
-- a mart grouping on the event's copy would report that wrong category with
-- total confidence, and no consistency check on the events could see it --
-- they all agree with each other. The disagreement between the two sources is
-- asserted by tests/assert_event_category_matches_products.sql.
with purchases as (
    select *
    from {{ ref('stg_events') }}
    where event_type = 'purchase'
)

select
    cast(purchases.event_at as date) as event_date,
    purchases.product_id,
    products.product_category,
    count(*) as num_purchases,
    sum(purchases.quantity) as units_sold,
    sum(purchases.price * purchases.quantity) as gross_revenue
from purchases
inner join {{ ref('products') }} as products
    on purchases.product_id = products.product_id
group by 1, 2, 3
order by event_date, gross_revenue desc
