select
    downtime_date,
    store_code,
    downtime_minutes
from {{ source('raw', 'fact_pos_downtime') }}
