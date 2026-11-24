select
    month,
    store_code,
    general_waste_kg,
    food_waste_kg,
    recycled_kg
from {{ source('raw', 'fact_waste_monthly') }}
