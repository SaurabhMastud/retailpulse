-- A run that reads a batch but loads, duplicates, and rejects nothing is
-- the shape a silently-broken pipeline actually produces (source went
-- empty, a step upstream failed quietly) -- row counts alone don't catch
-- it since "0 loaded" looks identical to "nothing new to load" without
-- also checking duplicates/rejected.
select *
from {{ ref('stg_pipeline_runs') }}
where ingested_at = (select max(ingested_at) from {{ ref('stg_pipeline_runs') }})
  and events_loaded = 0
  and duplicates = 0
  and rejected = 0
