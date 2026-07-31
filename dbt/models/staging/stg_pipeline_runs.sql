with source as (
    select * from {{ source('raw', 'pipeline_runs') }}
),

renamed as (
    select
        batch_id,
        source_file,
        events_read,
        events_loaded,
        duplicates,
        rejected,
        ingested_at,
        -- share of the batch that failed validation; the number worth alerting
        -- on, rather than the raw reject count which scales with batch size
        round(rejected * 1.0 / nullif(events_read, 0), 4) as reject_rate
    from source
)

select * from renamed
