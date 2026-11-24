select
    variance_date,
    store_code,
    cashier_id,
    expected_cash,
    actual_cash
from {{ source('raw', 'fact_cash_variance') }}
