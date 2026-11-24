-- Kalender harian + atribut musiman Bali
select
    c.date,
    extract(year from c.date)                    as year,
    date_trunc(c.date, month)                    as month,
    date_trunc(c.date, isoweek)                  as week_start,
    extract(dayofweek from c.date)               as day_of_week,  -- 1 = Minggu
    nullif(c.event, '')                          as event,
    c.is_nyepi,
    c.is_high_season
from {{ ref('bali_calendar') }} c
