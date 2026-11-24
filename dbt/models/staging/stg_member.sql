select
    member_id,
    home_store_code,
    age_group,
    gender,
    member_type,
    join_date
from {{ source('raw', 'dim_member') }}
