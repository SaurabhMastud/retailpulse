-- Events carry a product_category alongside product_id. The catalog
-- (dbt/seeds/products.csv) is the record of what a product actually is, so
-- the two have to agree.
--
-- This replaces assert_product_id_maps_to_one_category, which only checked the
-- events against each other. That test could not fail when *every* event for a
-- product named the same wrong category -- the exact case where a mart would
-- report a confidently wrong number. Checking against the dimension catches
-- both that and the inconsistency the old test covered, since two categories
-- for one product means at least one of them disagrees with the catalog.
--
-- Fails if this query returns rows. Events referencing a product the catalog
-- has never heard of are caught separately by the relationships test on
-- stg_events.product_id, so the join here is deliberately inner.
select
    events.product_id,
    events.product_category as event_category,
    products.product_category as catalog_category,
    count(*) as event_count
from {{ ref('stg_events') }} as events
inner join {{ ref('products') }} as products
    on events.product_id = products.product_id
where events.product_category is distinct from products.product_category
group by 1, 2, 3
