-- Grain: bulan PO x supplier
select
    date_trunc(po.po_date, month)                                   as month,
    po.supplier_id,
    s.supplier_name,
    s.lead_time_days,
    count(*)                                                        as po_lines,
    sum(po.qty_ordered)                                             as qty_ordered,
    sum(po.qty_received)                                            as qty_received,
    safe_divide(sum(po.qty_received), sum(po.qty_ordered))          as fill_rate,
    avg(if(po.received_date <= po.expected_date, 1, 0))             as on_time_rate,
    avg(date_diff(po.received_date, po.expected_date, day))         as avg_delay_days
from {{ ref('stg_purchase_order') }} po
join {{ ref('stg_supplier') }} s on s.supplier_id = po.supplier_id
group by 1, 2, 3, 4
