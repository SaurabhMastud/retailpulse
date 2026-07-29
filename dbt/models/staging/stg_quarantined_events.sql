with source as (
    select * from {{ source('raw', 'quarantined_events') }}
),

renamed as (
    select
        event_id,
        raw_event,
        error,
        quarantined_at
    from source
)

select * from renamed
