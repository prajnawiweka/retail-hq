-- Grain: bulan x SKU. Ringkas untuk dashboard (Top SKU OOS berdasarkan jumlah toko).
select
    date_trunc(week_start, month)                                as month,
    sku,
    product_name,
    category,
    supplier_id,
    count(distinct store_code)                                   as stores_carrying,
    count(distinct if(is_oos, store_code, null))                 as stores_oos,
    count(distinct if(is_soh_zero, store_code, null))            as stores_soh_zero,
    count(*)                                                     as store_weeks,
    countif(is_oos)                                              as oos_store_weeks,
    countif(is_soh_zero)                                         as soh_zero_store_weeks,
    countif(is_below_min)                                        as below_min_store_weeks,
    sum(days_oos)                                                as days_oos,
    sum(est_lost_sales)                                          as est_lost_sales
from {{ ref('mart_oos_weekly') }}
group by 1, 2, 3, 4, 5
