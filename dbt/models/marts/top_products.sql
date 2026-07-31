-- Product performance at a daily grain: one row per (event_date, product_id).
-- Kept at the finest useful grain rather than all-time, so a consumer can roll
-- up any window it wants (last 7 days, month to date) from the same table --
-- an all-time table can only answer one question.
with purchases as (
    select *
    from {{ ref('stg_events') }}
    where event_type = 'purchase'
)

select
    cast(event_at as date) as event_date,
    product_id,
    product_category,
    count(*) as num_purchases,
    sum(quantity) as units_sold,
    sum(price * quantity) as gross_revenue
from purchases
group by 1, 2, 3
order by event_date, gross_revenue desc
