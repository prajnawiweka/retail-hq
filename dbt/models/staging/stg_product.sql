select
    sku,
    product_name,
    category,
    subcategory,
    brand,
    supplier_id,
    cost_price,
    sell_price
from {{ source('raw', 'dim_product') }}
