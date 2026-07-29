-- Defense in depth: Python validation (src/ingestion/validate.py) already
-- rejects these at ingest time, but a direct-load path (backfill, manual
-- insert) could bypass it. A singular test fails if this query returns rows.
select *
from {{ ref('stg_events') }}
where event_type in ('add_to_cart', 'purchase')
  and (price is null or quantity is null or price < 0 or quantity <= 0)
