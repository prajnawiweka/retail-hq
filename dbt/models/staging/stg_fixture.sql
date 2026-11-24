select
    fixture_id,
    store_code,
    fixture_type,
    zone,
    shelf_count,
    length_cm
from {{ source('raw', 'dim_fixture') }}
