-- top_products carries product_category alongside product_id and groups by
-- both, which silently splits a product into two rows if the same product_id
-- ever arrives under two categories. The old `unique` test on top_products'
-- product_id caught that as a side effect; now that the mart is date-grained
-- it can't, so the invariant is asserted directly at the source.
select
    product_id,
    count(distinct product_category) as category_count
from {{ ref('stg_events') }}
group by product_id
having count(distinct product_category) > 1
