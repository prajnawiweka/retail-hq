select
    opname_date,
    store_code,
    sku,
    system_qty,
    physical_qty
from {{ source('raw', 'fact_stock_opname') }}
