select
    store_code,
    store_name,
    regency,
    district,
    location_type,
    am_name,
    ak_name,
    store_type,
    size_m2,
    open_date,
    status
from {{ source('raw', 'dim_store') }}
