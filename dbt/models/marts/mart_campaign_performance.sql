-- Grain: campaign.
-- Uplift memakai difference-in-differences supaya efek musiman (misal high season Jul) tidak
-- dihitung sebagai hasil campaign:
--   uplift = (kategori target selama / sebelum) / (kategori lain selama / sebelum) - 1
-- "Sebelum" = 28 hari sebelum campaign, dihitung per hari, di toko yang sama.
with c as (
    select *, date_diff(end_date, start_date, day) + 1 as campaign_days
    from {{ ref('stg_campaign') }}
),
daily as (
    select sales_date, store_code, category, net_sales, cogs
    from {{ ref('stg_sales_category_daily') }}
),
windows as (
    select
        c.campaign_id,
        d.category = c.target_category                                   as is_target,
        d.sales_date >= c.start_date                                     as is_during,
        sum(d.net_sales)                                                 as net_sales,
        sum(d.net_sales - d.cogs)                                        as gross_profit,
        count(distinct d.sales_date)                                     as days
    from c
    join daily d
      on d.sales_date between date_sub(c.start_date, interval 28 day) and c.end_date
     and (c.target_store_code is null or d.store_code = c.target_store_code)
    group by 1, 2, 3
),
w as (
    select
        campaign_id,
        sum(if(is_target and is_during, net_sales, 0))                         as target_sales_during,
        sum(if(is_target and is_during, days, 0))                              as days_during,
        safe_divide(sum(if(is_target and not is_during, net_sales, 0)),
                    sum(if(is_target and not is_during, days, 0)))             as target_daily_before,
        safe_divide(sum(if(is_target and not is_during, gross_profit, 0)),
                    sum(if(is_target and not is_during, net_sales, 0)))        as target_gm_pct,
        safe_divide(sum(if(not is_target and is_during, net_sales, 0)),
                    sum(if(not is_target and is_during, days, 0)))             as other_daily_during,
        safe_divide(sum(if(not is_target and not is_during, net_sales, 0)),
                    sum(if(not is_target and not is_during, days, 0)))         as other_daily_before
    from windows
    group by 1
),
calc as (
    select
        w.*,
        -- baseline = penjualan sebelum x tren kategori lain (musiman)
        w.target_daily_before * safe_divide(w.other_daily_during, w.other_daily_before) * w.days_during as baseline_sales
    from w
)
select
    c.campaign_id, c.campaign_name, c.channel, c.start_date, c.end_date, c.campaign_days,
    c.target_category, c.target_store_code, c.cost,
    k.target_sales_during                                                    as sales_during,
    k.baseline_sales,
    k.target_sales_during - k.baseline_sales                                 as incremental_sales,
    safe_divide(k.target_sales_during, k.baseline_sales) - 1                 as uplift_pct,
    (k.target_sales_during - k.baseline_sales) * k.target_gm_pct             as incremental_gross_profit,
    safe_divide((k.target_sales_during - k.baseline_sales) * k.target_gm_pct - c.cost, c.cost) as roi
from c
left join calc k on k.campaign_id = c.campaign_id
