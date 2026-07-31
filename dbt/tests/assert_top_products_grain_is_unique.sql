-- top_products is grained on (event_date, product_id). dbt's built-in `unique`
-- test only covers a single column, so the composite key gets a singular test
-- rather than a dbt_utils dependency for one assertion.
select
    event_date,
    product_id,
    count(*) as row_count
from {{ ref('top_products') }}
group by event_date, product_id
having count(*) > 1
