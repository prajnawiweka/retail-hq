select
    po_id,
    po_date,
    supplier_id,
    sku,
    qty_ordered,
    qty_received,
    expected_date,
    received_date
from {{ source('raw', 'fact_purchase_order') }}
