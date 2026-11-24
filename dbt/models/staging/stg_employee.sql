select
    employee_id,
    store_code,
    position,
    hire_date,
    exit_date,
    monthly_salary
from {{ source('raw', 'dim_employee') }}
