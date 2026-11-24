select
    audit_date,
    store_code,
    fixture_id,
    sku,
    planned_facings,
    actual_facings,
    price_tag_ok,
    shelf_talker_ok
from {{ source('raw', 'fact_display_audit') }}
