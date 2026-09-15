-- The generator spreads session starts over the last `--days` days
-- (default 14) counted from generation time, so a warehouse fed by real
-- runs should always have events within that same window of "now". If the
-- newest event has fallen further behind than that, no new batch has been
-- generated or ingested recently -- the failure a silently-stalled pipeline
-- actually produces, distinct from the volume guardrail (which only catches
-- a run that reads a batch and loads nothing).
select max(event_at) as newest_event_at
from {{ ref('stg_events') }}
having max(event_at) < current_timestamp - interval '{{ var("freshness_window_days", 14) }} days'
