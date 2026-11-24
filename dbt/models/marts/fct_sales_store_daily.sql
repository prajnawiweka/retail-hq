-- Grain: toko x hari buka. Tidak ada baris = toko tutup (Nyepi) atau belum buka.
select
    d.sales_date,
    d.store_code,
    d.gross_sales,
    d.net_sales,
    d.cogs,
    d.net_sales - d.cogs                                   as gross_profit,
    d.std,
    safe_divide(d.net_sales, d.std)                        as amb,
    d.qty_items,
    safe_divide(d.qty_items, d.std)                        as items_per_basket,
    d.sales_promo,
    safe_divide(d.sales_promo, d.net_sales)                as promo_share,
    d.std_promo,
    d.target_spd,
    safe_divide(d.net_sales, d.target_spd)                 as achievement,
    c.event,
    coalesce(c.is_high_season, false)                      as is_high_season
from {{ ref('stg_sales_daily') }} d
left join {{ ref('dim_date') }} c on c.date = d.sales_date
