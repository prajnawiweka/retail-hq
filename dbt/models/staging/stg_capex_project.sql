select
    project_id,
    store_code,
    project_type,
    capex_amount,
    start_date,
    open_date,
    status
from {{ source('raw', 'fact_capex_project') }}
