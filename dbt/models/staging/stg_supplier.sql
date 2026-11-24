select
    supplier_id,
    supplier_name,
    lead_time_days,
    payment_terms
from {{ source('raw', 'dim_supplier') }}
