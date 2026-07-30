with session_events as (
    select
        session_id,
        max(case when event_type = 'page_view' then 1 else 0 end) as has_page_view,
        max(case when event_type = 'add_to_cart' then 1 else 0 end) as has_add_to_cart,
        max(case when event_type = 'purchase' then 1 else 0 end) as has_purchase
    from {{ ref('stg_events') }}
    group by session_id
)

select
    count(*) as total_sessions,
    sum(has_page_view) as sessions_with_page_view,
    sum(has_add_to_cart) as sessions_with_add_to_cart,
    sum(has_purchase) as sessions_with_purchase,
    round(sum(has_add_to_cart) * 1.0 / nullif(sum(has_page_view), 0), 4) as view_to_cart_rate,
    round(sum(has_purchase) * 1.0 / nullif(sum(has_add_to_cart), 0), 4) as cart_to_purchase_rate
from session_events
