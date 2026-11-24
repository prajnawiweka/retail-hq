-- Grain: bulan x kasir (login POS per slot kasir)
with v as (
    select date_trunc(void_date, month) as month, store_code, cashier_id,
           count(*) as days, sum(void_count) as void_count, sum(void_value) as void_value,
           sum(refund_count) as refund_count, sum(refund_value) as refund_value
    from {{ ref('stg_pos_void') }}
    group by 1, 2, 3
),
c as (
    select date_trunc(variance_date, month) as month, cashier_id,
           sum(actual_cash - expected_cash) as cash_variance,
           countif(actual_cash < expected_cash) as short_days
    from {{ ref('stg_cash_variance') }}
    group by 1, 2
)
select
    v.*,
    safe_divide(v.void_count, v.days)   as void_per_day,
    safe_divide(v.refund_count, v.days) as refund_per_day,
    c.cash_variance,
    c.short_days
from v
left join c on c.month = v.month and c.cashier_id = v.cashier_id
