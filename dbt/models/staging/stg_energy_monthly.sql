select
    month,
    store_code,
    kwh_total,
    kwh_chiller,
    kwh_ac,
    energy_cost
from {{ source('raw', 'fact_energy_monthly') }}
