-- Grain: kontrak. Status per report_date (var di dbt_project.yml).
select
    k.*,
    s.store_name,
    s.regency,
    date_diff(k.end_date, date('{{ var("report_date") }}'), day) as days_to_expiry,
    case
        when k.end_date < date('{{ var("report_date") }}') then 'sudah berakhir'
        when date_diff(k.end_date, date('{{ var("report_date") }}'), day) <= 90  then '<= 90 hari'
        when date_diff(k.end_date, date('{{ var("report_date") }}'), day) <= 180 then '91-180 hari'
        else '> 180 hari'
    end as expiry_bucket,
    k.annual_value * (1 + k.escalation_pct / 100) as next_annual_value_if_renewed
from {{ ref('stg_contract') }} k
join {{ ref('stg_store') }} s on s.store_code = k.store_code
