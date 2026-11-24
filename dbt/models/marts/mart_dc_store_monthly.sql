-- Grain: bulan x toko (pengiriman dari DC Denpasar)
select
    date_trunc(ship_date, month)                                    as month,
    store_code,
    count(*)                                                        as shipments,
    sum(qty_requested)                                              as qty_requested,
    sum(qty_shipped)                                                as qty_shipped,
    safe_divide(sum(qty_shipped), sum(qty_requested))               as fill_rate,
    avg(if(delivered_date <= planned_date, 1, 0))                   as on_time_rate,
    sum(delivery_cost)                                              as delivery_cost,
    safe_divide(sum(delivery_cost), sum(qty_shipped))               as cost_per_unit
from {{ ref('stg_dc_shipment') }}
group by 1, 2
