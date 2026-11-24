select
    campaign_id,
    campaign_name,
    channel,
    start_date,
    end_date,
    cost,
    target_category,
    target_store_code
from {{ source('raw', 'fact_campaign') }}
