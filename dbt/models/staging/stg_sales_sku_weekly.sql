select
    week_start,
    store_code,
    sku,
    qty,
    net_sales,
    cogs
from {{ source('raw', 'fact_sales_sku_weekly') }}
