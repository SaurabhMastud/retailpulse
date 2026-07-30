with purchases as (
    select *
    from {{ ref('stg_events') }}
    where event_type = 'purchase'
)

select
    product_id,
    product_category,
    count(*) as num_purchases,
    sum(quantity) as units_sold,
    sum(price * quantity) as gross_revenue
from purchases
group by 1, 2
order by gross_revenue desc
