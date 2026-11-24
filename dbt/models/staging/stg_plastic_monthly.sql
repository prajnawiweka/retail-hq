select
    month,
    store_code,
    plastic_bags_used,
    plastic_bags_sold
from {{ source('raw', 'fact_plastic_monthly') }}
