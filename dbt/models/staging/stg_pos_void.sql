select
    void_date,
    store_code,
    cashier_id,
    void_count,
    void_value,
    refund_count,
    refund_value
from {{ source('raw', 'fact_pos_void') }}
