select
    shipment_id,
    ship_date,
    store_code,
    qty_requested,
    qty_shipped,
    planned_date,
    delivered_date,
    delivery_cost
from {{ source('raw', 'fact_dc_shipment') }}
