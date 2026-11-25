"""Tool Finance: gross profit, opex, EBITDA, rasio biaya, budget."""
from __future__ import annotations

from retailhq_agents import bq
from retailhq_agents.tools.common import STORE_FILTER, params, safe, scope

SM = "mart_store_monthly"

_FIN = """
    sum(net_sales) as net_sales,
    sum(gross_profit) as gross_profit,
    safe_divide(sum(gross_profit), sum(net_sales)) as gm_pct,
    sum(total_opex) as total_opex,
    sum(budget_opex) as budget_opex,
    safe_divide(sum(total_opex), sum(budget_opex)) as opex_vs_budget,
    sum(gross_profit) - sum(total_opex) as ebitda,
    safe_divide(sum(gross_profit) - sum(total_opex), sum(net_sales)) as ebitda_pct,
    safe_divide(sum(rent), sum(net_sales)) as rent_pct,
    safe_divide(sum(salary), sum(net_sales)) as labor_cost_pct,
    safe_divide(sum(utilities), sum(net_sales)) as utilities_pct,
    safe_divide(sum(promo_cost), sum(net_sales)) as promo_cost_pct
"""


@safe
def ringkasan_finance(start_month: str = "", end_month: str = "", regency: str = "", am_name: str = "") -> dict:
    """Ringkasan Finance untuk periode (bulan YYYY-MM; kosong = 12 bulan terakhir): net sales, gross profit,
    GM %, total opex vs budget, EBITDA, EBITDA %, dan rasio sewa/gaji/utilitas/promo terhadap sales,
    dibandingkan periode yang sama tahun lalu. Filter opsional regency dan am_name."""
    p = bq.period(start_month, end_month)
    sql = f"""
        select 'kini' as periode, {_FIN} from {bq.table(SM)}
        where month between @start and @end and {STORE_FILTER}
        union all
        select 'tahun_lalu', {_FIN} from {bq.table(SM)}
        where month between @py_start and @py_end and {STORE_FILTER}"""
    rows = {r.pop("periode"): r for r in bq.query(sql, **params(p, regency, am_name))}
    cur, py = rows.get("kini", {}), rows.get("tahun_lalu", {})
    return {
        **scope(p, regency, am_name),
        "kini": cur,
        "tahun_lalu": py,
        "pertumbuhan": {k: bq.growth(cur.get(k), py.get(k)) for k in ("net_sales", "gross_profit", "total_opex", "ebitda")},
    }


@safe
def profitabilitas_toko(
    urutan: str = "terendah", limit: int = 15, start_month: str = "", end_month: str = "", regency: str = ""
) -> dict:
    """Ranking toko berdasarkan EBITDA % (urutan 'terendah' atau 'tertinggi', limit maks. 50).
    Field toko_ebitda_negatif = JUMLAH TOTAL toko dengan EBITDA negatif di periode; daftar 'toko' bisa
    lebih pendek karena dibatasi limit. Selalu laporkan jumlah total dari toko_ebitda_negatif.
    Tiap toko: net sales, EBITDA, EBITDA %, rent %, labor cost %, opex vs budget, lokasi, dan berapa bulan
    EBITDA-nya negatif dalam periode."""
    order = "asc" if urutan.lower().startswith("terendah") or urutan.lower() == "asc" else "desc"
    p = bq.period(start_month, end_month)
    sql = f"""
        select store_code, any_value(regency) as regency, any_value(location_type) as location_type,
               {_FIN},
               countif(gross_profit - total_opex < 0) as bulan_ebitda_negatif,
               count(*) as jumlah_bulan
        from {bq.table(SM)}
        where month between @start and @end and {STORE_FILTER}
        group by store_code
        order by ebitda_pct {order}
        limit @lim"""
    rows = bq.query(sql, **params(p, regency, lim=max(1, min(int(limit), 50))))
    for r in rows:
        for k in ("gross_profit", "budget_opex", "utilities_pct", "promo_cost_pct"):
            r.pop(k, None)
    neg = bq.query(
        f"""select count(*) as toko_ebitda_negatif from (
              select store_code from {bq.table(SM)}
              where month between @start and @end and {STORE_FILTER}
              group by store_code having sum(gross_profit) - sum(total_opex) < 0)""",
        **params(p, regency),
    )[0]
    return {**scope(p, regency), **neg, "toko": rows}


@safe
def tren_opex_bulanan(start_month: str = "", end_month: str = "", regency: str = "") -> dict:
    """Per bulan: net sales, komponen opex (gaji, sewa, utilitas, maintenance, promo, IT, lainnya),
    total opex vs budget, dan EBITDA %. Untuk melihat biaya mana yang naik dan kapan."""
    p = bq.period(start_month, end_month)
    sql = f"""
        select month, sum(net_sales) as net_sales, sum(salary) as gaji, sum(rent) as sewa,
               sum(utilities) as utilitas, sum(maintenance) as maintenance, sum(promo_cost) as promo,
               sum(it_cost) as it, sum(other_cost) as lainnya, sum(total_opex) as total_opex,
               sum(budget_opex) as budget_opex,
               safe_divide(sum(gross_profit) - sum(total_opex), sum(net_sales)) as ebitda_pct
        from {bq.table(SM)}
        where month between @start and @end and {STORE_FILTER}
        group by month order by month"""
    return {**scope(p, regency), "bulan": bq.query(sql, **params(p, regency))}


TOOLS = [ringkasan_finance, profitabilitas_toko, tren_opex_bulanan]
