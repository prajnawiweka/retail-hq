select
    store_code,
    sku,
    display_type,
    start_date,
    end_date
from {{ source('raw', 'fact_secondary_display') }}
