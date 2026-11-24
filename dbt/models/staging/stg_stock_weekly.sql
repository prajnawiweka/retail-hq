select
    week_start,
    store_code,
    sku,
    soh,
    min_stock,
    oos_flag,
    days_oos
from {{ source('raw', 'fact_stock_weekly') }}
