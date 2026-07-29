with source as (
    select * from {{ source('raw', 'raw_events') }}
),

renamed as (
    select
        event_id,
        event_type,
        user_id,
        session_id,
        product_id,
        product_category,
        price,
        quantity,
        "timestamp" as event_at
    from source
)

select * from renamed
