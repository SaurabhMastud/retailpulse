with purchases as (
    select *
    from {{ ref('stg_events') }}
    where event_type = 'purchase'
)

select
    cast(event_at as date) as event_date,
    count(*) as num_purchases,
    count(distinct user_id) as num_purchasing_users,
    sum(price * quantity) as gross_revenue
from purchases
group by 1
order by 1
