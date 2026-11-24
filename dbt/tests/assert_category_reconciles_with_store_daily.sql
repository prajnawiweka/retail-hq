-- Total kategori harian harus sama persis dengan total toko harian
with c as (
    select sales_date, store_code, sum(net_sales) as net_sales, sum(cogs) as cogs
    from {{ ref('stg_sales_category_daily') }}
    group by 1, 2
)
select d.sales_date, d.store_code, d.net_sales, c.net_sales as net_sales_category
from {{ ref('stg_sales_daily') }} d
left join c on c.sales_date = d.sales_date and c.store_code = d.store_code
where c.net_sales is null or d.net_sales != c.net_sales or d.cogs != c.cogs
