-- Grain: bulan x toko. Tabel utama untuk dashboard dan agent (semua department).
with sales as (
    select
        date_trunc(sales_date, month) as month,
        store_code,
        count(*)            as open_days,
        sum(net_sales)      as net_sales,
        sum(gross_profit)   as gross_profit,
        sum(std)            as std,
        sum(qty_items)      as qty_items,
        sum(sales_promo)    as sales_promo,
        sum(target_spd)     as target_sales
    from {{ ref('fct_sales_store_daily') }}
    group by 1, 2
),
opex as (
    select *, rent + salary + utilities + maintenance + promo_cost + it_cost + other_cost as total_opex
    from {{ ref('stg_opex_monthly') }}
),
shift as (
    select date_trunc(work_date, month) as month, store_code,
           sum(hours_worked) as hours_worked, sum(overtime_hours) as overtime_hours
    from {{ ref('stg_shift') }}
    group by 1, 2
),
headcount as (
    select s.month, s.store_code,
           countif(e.hire_date <= last_day(s.month) and (e.exit_date is null or e.exit_date > last_day(s.month))) as headcount_end,
           countif(e.exit_date between s.month and last_day(s.month)) as exits
    from sales s
    join {{ ref('stg_employee') }} e on e.store_code = s.store_code
    group by 1, 2
),
stock as (
    select date_trunc(week_start, month) as month, store_code,
           count(*) as sku_weeks, sum(oos_flag) as oos_sku_weeks, countif(soh = 0) as soh_zero_sku_weeks
    from {{ ref('stg_stock_weekly') }}
    group by 1, 2
),
opname as (
    select date_trunc(o.opname_date, month) as month, o.store_code,
           sum((o.system_qty - o.physical_qty) * p.cost_price) as opname_loss_value,
           sum(o.system_qty * p.cost_price)                    as opname_system_value
    from {{ ref('stg_stock_opname') }} o
    join {{ ref('stg_product') }} p on p.sku = o.sku
    group by 1, 2
),
writeoff as (
    select date_trunc(writeoff_date, month) as month, store_code,
           sum(value) as writeoff_value,
           sum(if(reason = 'hilang', value, 0)) as writeoff_hilang_value,
           sum(if(reason = 'expired', value, 0)) as writeoff_expired_value
    from {{ ref('stg_writeoff') }}
    group by 1, 2
),
pos as (
    select date_trunc(void_date, month) as month, store_code,
           sum(void_value) as void_value, sum(refund_value) as refund_value
    from {{ ref('stg_pos_void') }}
    group by 1, 2
),
cash as (
    select date_trunc(variance_date, month) as month, store_code,
           sum(actual_cash - expected_cash) as cash_variance,
           countif(actual_cash < expected_cash) as cash_short_count
    from {{ ref('stg_cash_variance') }}
    group by 1, 2
),
tickets as (
    select date(datetime_trunc(opened_at, month)) as month, store_code,
           count(*) as it_tickets,
           avg(datetime_diff(resolved_at, opened_at, minute)) / 60 as avg_resolution_hours
    from {{ ref('stg_it_ticket') }}
    group by 1, 2
),
downtime as (
    select date_trunc(downtime_date, month) as month, store_code, sum(downtime_minutes) as pos_downtime_minutes
    from {{ ref('stg_pos_downtime') }}
    group by 1, 2
),
display as (
    select date_trunc(audit_date, month) as month, store_code,
           avg(if(actual_facings >= planned_facings, 1, 0)) as display_compliance,
           count(*) as audited_items,
           countif(actual_facings >= planned_facings) as compliant_items
    from {{ ref('stg_display_audit') }}
    group by 1, 2
)
select
    s.month,
    s.store_code,
    st.regency, st.location_type, st.store_type, st.am_name, st.ak_name, st.size_m2,
    s.open_days,
    -- Operation & Merchandise
    s.net_sales,
    s.gross_profit,
    safe_divide(s.gross_profit, s.net_sales)                          as gm_pct,
    safe_divide(s.net_sales, s.open_days)                             as spd,
    s.std,
    safe_divide(s.std, s.open_days)                                   as std_per_day,
    safe_divide(s.net_sales, s.std)                                   as amb,
    safe_divide(s.sales_promo, s.net_sales)                           as promo_share,
    s.target_sales,
    safe_divide(s.net_sales, s.target_sales)                          as achievement,
    ly.net_sales                                                      as net_sales_ly,
    safe_divide(safe_divide(s.net_sales, s.open_days), safe_divide(ly.net_sales, ly.open_days)) - 1 as spd_yoy_growth,
    -- Finance
    o.rent, o.salary, o.utilities, o.maintenance, o.promo_cost, o.it_cost, o.other_cost, o.total_opex,
    s.gross_profit - o.total_opex                                     as ebitda,
    safe_divide(s.gross_profit - o.total_opex, s.net_sales)           as ebitda_pct,
    safe_divide(o.rent, s.net_sales)                                  as rent_pct,
    safe_divide(o.salary, s.net_sales)                                as labor_cost_pct,
    b.budget_sales, b.budget_opex,
    -- HR
    h.headcount_end,
    h.exits,
    safe_divide(h.exits, h.headcount_end)                             as turnover_rate,
    sh.hours_worked,
    sh.overtime_hours,
    safe_divide(sh.overtime_hours, sh.hours_worked)                   as overtime_ratio,
    safe_divide(s.net_sales, sh.hours_worked + sh.overtime_hours)     as sales_per_labor_hour,
    -- Supply Chain
    k.sku_weeks,
    k.oos_sku_weeks,
    k.soh_zero_sku_weeks,
    safe_divide(k.oos_sku_weeks, k.sku_weeks)                         as oos_rate,
    safe_divide(k.soh_zero_sku_weeks, k.sku_weeks)                    as soh_zero_rate,
    -- Loss Prevention
    op.opname_loss_value,
    safe_divide(op.opname_loss_value, op.opname_system_value)         as opname_shrink_pct,
    coalesce(w.writeoff_value, 0)                                     as writeoff_value,
    coalesce(w.writeoff_hilang_value, 0)                              as writeoff_hilang_value,
    coalesce(w.writeoff_expired_value, 0)                             as writeoff_expired_value,
    safe_divide(w.writeoff_value, s.net_sales)                        as writeoff_pct,
    p.void_value, p.refund_value,
    c.cash_variance, c.cash_short_count,
    -- IT
    coalesce(t.it_tickets, 0)                                         as it_tickets,
    t.avg_resolution_hours,
    coalesce(dt.pos_downtime_minutes, 0)                              as pos_downtime_minutes,
    -- ESG
    e.kwh_total, e.kwh_chiller, e.kwh_ac,
    safe_divide(e.kwh_total, st.size_m2)                              as kwh_per_m2,
    safe_divide(e.energy_cost, s.net_sales)                           as energy_cost_pct,
    ws.general_waste_kg, ws.food_waste_kg, ws.recycled_kg,
    safe_divide(ws.recycled_kg, ws.general_waste_kg + ws.food_waste_kg) as recycle_rate,
    pl.plastic_bags_used, pl.plastic_bags_sold,
    -- Planogram
    d.display_compliance,
    d.audited_items,
    d.compliant_items
from sales s
join {{ ref('dim_store') }} st on st.store_code = s.store_code
left join sales ly on ly.store_code = s.store_code and ly.month = date_sub(s.month, interval 1 year)
left join opex o                                  on o.store_code = s.store_code and o.month = s.month
left join {{ ref('stg_budget_monthly') }} b       on b.store_code = s.store_code and b.month = s.month
left join headcount h                             on h.store_code = s.store_code and h.month = s.month
left join shift sh                                on sh.store_code = s.store_code and sh.month = s.month
left join stock k                                 on k.store_code = s.store_code and k.month = s.month
left join opname op                               on op.store_code = s.store_code and op.month = s.month
left join writeoff w                              on w.store_code = s.store_code and w.month = s.month
left join pos p                                   on p.store_code = s.store_code and p.month = s.month
left join cash c                                  on c.store_code = s.store_code and c.month = s.month
left join tickets t                               on t.store_code = s.store_code and t.month = s.month
left join downtime dt                             on dt.store_code = s.store_code and dt.month = s.month
left join {{ ref('stg_energy_monthly') }} e       on e.store_code = s.store_code and e.month = s.month
left join {{ ref('stg_waste_monthly') }} ws       on ws.store_code = s.store_code and ws.month = s.month
left join {{ ref('stg_plastic_monthly') }} pl     on pl.store_code = s.store_code and pl.month = s.month
left join display d                               on d.store_code = s.store_code and d.month = s.month
