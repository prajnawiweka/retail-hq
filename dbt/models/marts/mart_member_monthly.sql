-- Grain: bulan x tipe member (lokal/turis/ekspat)
with act as (
    select mm.month, mm.member_id, m.member_type,
           sum(mm.visits) as visits, sum(mm.net_sales) as net_sales
    from {{ ref('stg_member_monthly') }} mm
    join {{ ref('stg_member') }} m on m.member_id = mm.member_id
    group by 1, 2, 3
),
agg as (
select
    a.month,
    a.member_type,
    count(*)                                                       as active_members,
    countif(prev.member_id is not null)                            as retained_from_last_month,
    sum(a.visits)                                                  as visits,
    sum(a.net_sales)                                               as net_sales,
    safe_divide(sum(a.net_sales), sum(a.visits))                   as amb_member
from act a
left join act prev
    on prev.member_id = a.member_id
   and prev.month = date_sub(a.month, interval 1 month)
group by 1, 2
)
select
    agg.*,
    safe_divide(retained_from_last_month,
                lag(active_members) over (partition by member_type order by month)) as retention_rate
from agg
