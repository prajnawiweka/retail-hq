-- Grain: bulan x toko (audit display). Merchandise: desain; Operation: kepatuhan.
select
    date_trunc(a.audit_date, month)                              as month,
    a.store_code,
    s.am_name,
    s.ak_name,
    s.regency, s.location_type, s.store_type,
    count(*)                                                     as audited_items,
    countif(a.actual_facings >= a.planned_facings)               as compliant_items,
    avg(if(a.actual_facings >= a.planned_facings, 1, 0))         as facing_compliance,
    avg(if(a.price_tag_ok, 1, 0))                                as price_tag_ok_rate,
    avg(if(a.shelf_talker_ok, 1, 0))                             as shelf_talker_ok_rate,
    sum(greatest(a.planned_facings - a.actual_facings, 0))       as missing_facings
from {{ ref('stg_display_audit') }} a
join {{ ref('stg_store') }} s on s.store_code = a.store_code
group by 1, 2, 3, 4, 5, 6, 7
