-- Grain: bulan x toko (pengiriman dari DC Denpasar)
select
    date_trunc(d.ship_date, month)                                  as month,
    d.store_code,
    st.regency, st.am_name, st.ak_name, st.location_type, st.store_type,
    count(*)                                                        as shipments,
    countif(d.delivered_date <= d.planned_date)                     as on_time_shipments,
    sum(d.qty_requested)                                            as qty_requested,
    sum(d.qty_shipped)                                              as qty_shipped,
    safe_divide(sum(d.qty_shipped), sum(d.qty_requested))           as fill_rate,
    avg(if(d.delivered_date <= d.planned_date, 1, 0))               as on_time_rate,
    sum(d.delivery_cost)                                            as delivery_cost,
    safe_divide(sum(d.delivery_cost), sum(d.qty_shipped))           as cost_per_unit
from {{ ref('stg_dc_shipment') }} d
join {{ ref('stg_store') }} st on st.store_code = d.store_code
where d.ship_date >= '2024-11-01'  -- kiriman stok awal akhir Okt 2024 di luar periode laporan
group by 1, 2, 3, 4, 5, 6, 7
