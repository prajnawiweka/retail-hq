select
    asset_id,
    store_code,
    asset_type,
    purchase_date,
    status
from {{ source('raw', 'dim_it_asset') }}
