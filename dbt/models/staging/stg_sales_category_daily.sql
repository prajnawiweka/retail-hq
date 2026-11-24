select
    sales_date,
    store_code,
    category,
    net_sales,
    cogs,
    qty
from {{ source('raw', 'fact_sales_category_daily') }}
