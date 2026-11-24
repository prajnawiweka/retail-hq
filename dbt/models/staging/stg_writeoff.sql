select
    writeoff_date,
    store_code,
    sku,
    qty,
    reason,
    value
from {{ source('raw', 'fact_writeoff') }}
