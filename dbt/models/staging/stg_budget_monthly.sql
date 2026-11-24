select
    month,
    store_code,
    budget_sales,
    budget_opex
from {{ source('raw', 'fact_budget_monthly') }}
