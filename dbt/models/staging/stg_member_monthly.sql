select
    month,
    member_id,
    store_code,
    visits,
    net_sales,
    top_category
from {{ source('raw', 'fact_member_monthly') }}
