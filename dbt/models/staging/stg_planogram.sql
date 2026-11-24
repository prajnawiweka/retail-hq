select
    store_code,
    fixture_id,
    shelf_level,
    sku,
    facings,
    position,
    effective_from,
    effective_to
from {{ source('raw', 'fact_planogram') }}
