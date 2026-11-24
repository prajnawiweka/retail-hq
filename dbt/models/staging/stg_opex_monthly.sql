select
    month,
    store_code,
    rent,
    salary,
    utilities,
    maintenance,
    promo_cost,
    it_cost,
    other_cost
from {{ source('raw', 'fact_opex_monthly') }}
