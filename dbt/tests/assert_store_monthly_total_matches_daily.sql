-- Total net_sales mart bulanan harus sama dengan sumber harian
select m.total_mart, d.total_daily
from (select sum(net_sales) as total_mart from {{ ref('mart_store_monthly') }}) m
cross join (select sum(net_sales) as total_daily from {{ ref('stg_sales_daily') }}) d
where m.total_mart != d.total_daily
