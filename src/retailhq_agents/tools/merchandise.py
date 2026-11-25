"""Tool Merchandise: kinerja kategori, margin, dan kepatuhan planogram."""
from __future__ import annotations

from retailhq_agents import bq
from retailhq_agents.tools.common import STORE_FILTER, params, safe, scope


@safe
def kinerja_kategori(start_month: str = "", end_month: str = "", regency: str = "", am_name: str = "") -> dict:
    """Per kategori: net sales, kontribusi ke total, gross margin %, dan pertumbuhan vs periode sama tahun lalu.
    Urut net sales tertinggi."""
    p = bq.period(start_month, end_month)
    t = bq.table("mart_category_monthly")
    sql = f"""
        with c as (
          select category, sum(net_sales) as net_sales, sum(gross_profit) as gross_profit
          from {t} where month between @start and @end and {STORE_FILTER} group by category),
        l as (
          select category, sum(net_sales) as net_sales_py
          from {t} where month between @py_start and @py_end and {STORE_FILTER} group by category)
        select c.category, c.net_sales,
               safe_divide(c.net_sales, sum(c.net_sales) over ()) as kontribusi,
               safe_divide(c.gross_profit, c.net_sales) as gm_pct,
               safe_divide(c.net_sales, l.net_sales_py) - 1 as yoy
        from c left join l using (category)
        order by c.net_sales desc"""
    return {**scope(p, regency, am_name), "kategori": bq.query(sql, **params(p, regency, am_name))}


@safe
def tren_kategori_bulanan(category: str, start_month: str = "", end_month: str = "", regency: str = "") -> dict:
    """Tren per bulan satu kategori (misal 'Minuman'): net sales, GM %, kontribusi ke toko, dan net sales bulan
    yang sama tahun lalu. Untuk melihat kapan kategori mulai turun/naik."""
    p = bq.period(start_month, end_month)
    sql = f"""
        select month, sum(net_sales) as net_sales, sum(net_sales_ly) as net_sales_tahun_lalu,
               safe_divide(sum(net_sales), sum(net_sales_ly)) - 1 as yoy,
               safe_divide(sum(gross_profit), sum(net_sales)) as gm_pct
        from {bq.table('mart_category_monthly')}
        where month between @start and @end and lower(category) = lower(@cat) and {STORE_FILTER}
        group by month order by month"""
    rows = bq.query(sql, **params(p, regency, cat=category.strip()))
    if not rows:
        return {"error": f"Kategori '{category}' tidak ditemukan. Panggil kinerja_kategori untuk daftar nama kategori."}
    return {**scope(p, regency), "kategori": category, "bulan": rows}


@safe
def kepatuhan_planogram(start_month: str = "", end_month: str = "", per: str = "am_name") -> dict:
    """Kepatuhan planogram dari audit display: facing sesuai rencana, price tag benar, shelf talker benar,
    dan jumlah facing yang kurang. per: am_name | regency | store_code. Urut kepatuhan facing terendah."""
    if per not in {"am_name", "regency", "store_code"}:
        raise ValueError("per harus am_name, regency, atau store_code")
    p = bq.period(start_month, end_month)
    sql = f"""
        select {per}, count(distinct store_code) as toko,
               safe_divide(sum(compliant_items), sum(audited_items)) as facing_compliance,
               safe_divide(sum(price_tag_ok_rate * audited_items), sum(audited_items)) as price_tag_ok,
               safe_divide(sum(shelf_talker_ok_rate * audited_items), sum(audited_items)) as shelf_talker_ok,
               sum(missing_facings) as facing_kurang
        from {bq.table('mart_planogram_compliance_monthly')}
        where month between @start and @end
        group by {per} order by facing_compliance limit 50"""
    return {"periode": p["label"], "per": per, "hasil": bq.query(sql, start=p["start"], end=p["end"])}


TOOLS = [kinerja_kategori, tren_kategori_bulanan, kepatuhan_planogram]
