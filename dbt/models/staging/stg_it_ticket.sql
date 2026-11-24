select
    ticket_id,
    store_code,
    category,
    priority,
    opened_at,
    resolved_at
from {{ source('raw', 'fact_it_ticket') }}
