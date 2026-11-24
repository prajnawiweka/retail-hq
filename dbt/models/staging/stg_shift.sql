select
    work_date,
    store_code,
    employee_id,
    hours_worked,
    overtime_hours
from {{ source('raw', 'fact_shift') }}
