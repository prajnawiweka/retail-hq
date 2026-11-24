-- Grain: proyek capex. Payback = capex / rata-rata EBITDA bulanan sejak buka (hanya toko baru).
with perf as (
    select store_code,
           count(*)          as months_open,
           avg(ebitda)       as avg_monthly_ebitda,
           avg(spd)          as avg_spd,
           avg(achievement)  as avg_achievement
    from {{ ref('mart_store_monthly') }}
    group by 1
)
select
    p.*,
    s.store_name, s.regency, s.location_type,
    f.months_open, f.avg_spd, f.avg_achievement, f.avg_monthly_ebitda,
    if(p.project_type = 'baru' and f.avg_monthly_ebitda > 0,
       safe_divide(p.capex_amount, f.avg_monthly_ebitda), null)  as payback_months
from {{ ref('stg_capex_project') }} p
join {{ ref('stg_store') }} s on s.store_code = p.store_code
left join perf f on f.store_code = p.store_code
