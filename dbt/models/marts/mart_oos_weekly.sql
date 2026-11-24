-- Grain: minggu x toko x SKU. Membedakan OOS, SOH 0, dan di bawah min stock.
with base as (
    select
        k.week_start, k.store_code, k.sku,
        p.product_name, p.category, p.supplier_id,
        k.soh, k.min_stock, k.days_oos,
        k.oos_flag = 1          as is_oos,
        k.soh = 0               as is_soh_zero,
        k.soh < k.min_stock     as is_below_min,
        coalesce(s.net_sales, 0) as net_sales,
        coalesce(s.qty, 0)       as qty
    from {{ ref('stg_stock_weekly') }} k
    join {{ ref('stg_product') }} p on p.sku = k.sku
    left join {{ ref('stg_sales_sku_weekly') }} s
        on s.week_start = k.week_start and s.store_code = k.store_code and s.sku = k.sku
),
normal as (
    -- rata-rata penjualan mingguan saat tidak OOS, sebagai dasar estimasi lost sales
    select store_code, sku, avg(net_sales) as avg_weekly_sales_normal
    from base
    where not is_oos
    group by 1, 2
)
select
    b.*,
    n.avg_weekly_sales_normal,
    if(b.is_oos, n.avg_weekly_sales_normal * b.days_oos / 7, 0) as est_lost_sales
from base b
left join normal n on n.store_code = b.store_code and n.sku = b.sku
