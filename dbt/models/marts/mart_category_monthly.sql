-- Grain: bulan x toko x kategori
with m as (
    select
        date_trunc(sales_date, month) as month,
        store_code,
        category,
        sum(net_sales) as net_sales,
        sum(cogs)      as cogs,
        sum(qty)       as qty
    from {{ ref('stg_sales_category_daily') }}
    group by 1, 2, 3
)
select
    m.*,
    st.regency, st.am_name, st.ak_name, st.location_type, st.store_type,
    m.net_sales - m.cogs                                                  as gross_profit,
    safe_divide(m.net_sales - m.cogs, m.net_sales)                        as gm_pct,
    safe_divide(m.net_sales, sum(m.net_sales) over (partition by m.month, m.store_code)) as share_of_store,
    ly.net_sales                                                          as net_sales_ly,
    safe_divide(m.net_sales - ly.net_sales, ly.net_sales)                 as yoy_growth
from m
join {{ ref('stg_store') }} st on st.store_code = m.store_code
left join m ly
    on ly.store_code = m.store_code
   and ly.category = m.category
   and ly.month = date_sub(m.month, interval 1 year)
