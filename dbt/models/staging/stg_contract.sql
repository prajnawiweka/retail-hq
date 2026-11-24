select
    contract_id,
    store_code,
    vendor_name,
    contract_type,
    start_date,
    end_date,
    annual_value,
    escalation_pct,
    status
from {{ source('raw', 'dim_contract') }}
