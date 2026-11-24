select
    sales_date,
    store_code,
    gross_sales,
    net_sales,
    cogs,
    std,
    qty_items,
    sales_promo,
    std_promo,
    target_spd
from {{ source('raw', 'fact_sales_daily') }}
