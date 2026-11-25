"""Tool Operation: sales, SPD, STD, AMB, achievement, display compliance."""
from __future__ import annotations

from retailhq_agents import bq
from retailhq_agents.tools.common import STORE_FILTER, params, safe, scope

SM = "mart_store_monthly"

_KPI = """
    sum(net_sales) as net_sales,
    sum(target_sales) as target_sales,
    safe_divide(sum(net_sales), sum(target_sales)) as achievement,
    safe_divide(sum(net_sales), sum(open_days)) as spd,
    safe_divide(sum(std), sum(open_days)) as std_per_hari,
    safe_divide(sum(net_sales), sum(std)) as amb,
    safe_divide(sum(compliant_items), sum(audited_items)) as display_compliance,
    countif(net_sales >= target_sales) as toko_bulan_capai_target,
    count(*) as toko_bulan
"""


@safe
def ringkasan_operation(start_month: str = "", end_month: str = "", regency: str = "", am_name: str = "") -> dict:
    """Ringkasan KPI Operation untuk periode (format bulan YYYY-MM; kosong = 12 bulan terakhir).

    Mengembalikan net_sales, target, achievement, SPD (sales per hari per toko), STD per hari,
    AMB (rata-rata belanja per struk), display compliance, jumlah toko-bulan capai target,
    beserta nilai periode yang sama tahun lalu dan pertumbuhannya. Filter opsional: regency
    (kabupaten, misal 'Badung') dan am_name (nama Area Manager).
    """
    p = bq.period(start_month, end_month)
    sql = f"""
        select 'kini' as periode, {_KPI} from {bq.table(SM)}
        where month between @start and @end and {STORE_FILTER}
        union all
        select 'tahun_lalu', {_KPI} from {bq.table(SM)}
        where month between @py_start and @py_end and {STORE_FILTER}"""
    rows = {r.pop("periode"): r for r in bq.query(sql, **params(p, regency, am_name))}
    cur, py = rows.get("kini", {}), rows.get("tahun_lalu", {})
    return {
        **scope(p, regency, am_name),
        "kini": cur,
        "tahun_lalu": py,
        "pertumbuhan": {k: bq.growth(cur.get(k), py.get(k)) for k in ("net_sales", "spd", "std_per_hari", "amb")},
    }


_METRICS = {
    "achievement": "achievement",
    "spd": "spd",
    "net_sales": "net_sales",
    "spd_yoy": "spd_yoy",
    "display_compliance": "display_compliance",
}


@safe
def ranking_toko(
    metric: str = "achievement",
    urutan: str = "terendah",
    limit: int = 10,
    start_month: str = "",
    end_month: str = "",
    regency: str = "",
    am_name: str = "",
) -> dict:
    """Ranking toko pada satu metrik untuk periode.

    metric: achievement | spd | net_sales | spd_yoy (pertumbuhan SPD vs tahun lalu) | display_compliance.
    urutan: 'terendah' atau 'tertinggi'. limit: jumlah toko (maks. 50).
    Setiap baris berisi store_code, regency, am_name, net_sales, achievement, spd, spd_yoy, display_compliance.
    """
    if metric not in _METRICS:
        raise ValueError(f"metric harus salah satu dari {', '.join(_METRICS)}")
    order = "asc" if urutan.lower().startswith("terendah") or urutan.lower() == "asc" else "desc"
    p = bq.period(start_month, end_month)
    sql = f"""
        with cur as (
          select store_code, any_value(regency) as regency, any_value(am_name) as am_name,
                 sum(net_sales) as net_sales,
                 safe_divide(sum(net_sales), sum(target_sales)) as achievement,
                 safe_divide(sum(net_sales), sum(open_days)) as spd,
                 safe_divide(sum(compliant_items), sum(audited_items)) as display_compliance
          from {bq.table(SM)} where month between @start and @end and {STORE_FILTER}
          group by store_code),
        py as (
          select store_code, safe_divide(sum(net_sales), sum(open_days)) as spd_py
          from {bq.table(SM)} where month between @py_start and @py_end group by store_code)
        select cur.*, safe_divide(cur.spd, py.spd_py) - 1 as spd_yoy
        from cur left join py using (store_code)
        order by {_METRICS[metric]} {order} nulls last
        limit @lim"""
    rows = bq.query(sql, **params(p, regency, am_name, lim=max(1, min(int(limit), 50))))
    return {**scope(p, regency, am_name), "metric": metric, "urutan": urutan, "toko": rows}


@safe
def kinerja_per_am(start_month: str = "", end_month: str = "", regency: str = "") -> dict:
    """KPI per Area Manager (AM) dan Area Koordinator (AK): jumlah toko, net sales, achievement,
    SPD, display compliance, dan pertumbuhan net sales vs tahun lalu."""
    p = bq.period(start_month, end_month)
    sql = f"""
        with cur as (
          select am_name, any_value(ak_name) as ak_name, count(distinct store_code) as toko, {_KPI}
          from {bq.table(SM)} where month between @start and @end and {STORE_FILTER}
          group by am_name),
        py as (
          select am_name, sum(net_sales) as net_sales_py
          from {bq.table(SM)} where month between @py_start and @py_end and {STORE_FILTER}
          group by am_name)
        select cur.* except (toko_bulan), safe_divide(cur.net_sales, py.net_sales_py) - 1 as net_sales_yoy
        from cur left join py using (am_name)
        order by achievement"""
    return {**scope(p, regency), "am": bq.query(sql, **params(p, regency))}


@safe
def tren_bulanan_toko(store_code: str, start_month: str = "", end_month: str = "") -> dict:
    """Tren per bulan satu toko (misal 'DPS02'): net sales, target, achievement, SPD, dan SPD tahun lalu
    di bulan yang sama. Dipakai untuk melihat kapan penurunan mulai terjadi."""
    p = bq.period(start_month, end_month)
    sql = f"""
        select c.month, c.regency, c.am_name, c.net_sales, c.target_sales,
               safe_divide(c.net_sales, c.target_sales) as achievement,
               safe_divide(c.net_sales, c.open_days) as spd,
               safe_divide(l.net_sales, l.open_days) as spd_tahun_lalu,
               safe_divide(c.compliant_items, c.audited_items) as display_compliance
        from {bq.table(SM)} c
        left join {bq.table(SM)} l
          on l.store_code = c.store_code and l.month = date_sub(c.month, interval 1 year)
        where c.store_code = @store and c.month between @start and @end
        order by c.month"""
    rows = bq.query(sql, **params(p, store=store_code.strip().upper()))
    if not rows:
        return {"error": f"Toko {store_code} tidak ditemukan di periode {p['label']}"}
    return {"store_code": store_code.upper(), "periode": p["label"], "bulan": rows}


TOOLS = [ringkasan_operation, ranking_toko, kinerja_per_am, tren_bulanan_toko]
