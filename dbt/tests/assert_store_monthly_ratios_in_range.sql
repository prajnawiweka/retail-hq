-- Rasio harus masuk akal; baris yang muncul = data perlu dicek
select month, store_code, gm_pct, achievement, oos_rate, display_compliance
from {{ ref('mart_store_monthly') }}
where gm_pct not between 0 and 1
   or achievement not between 0 and 3
   or oos_rate not between 0 and 1
   or display_compliance not between 0 and 1
   or open_days not between 1 and 31
