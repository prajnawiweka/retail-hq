select
    s.*,
    date_diff(date('{{ var("report_date") }}'), s.open_date, month) as store_age_months,
    s.open_date >= '2024-11-01'                                     as is_new_store
from {{ ref('stg_store') }} s
