"""Tool DC: kinerja pengiriman DC Denpasar ke toko."""
from __future__ import annotations

from retailhq_agents import bq
from retailhq_agents.tools.common import safe
from retailhq_agents.tools.supply_chain import dc_per_kabupaten


@safe
def tren_dc_bulanan(start_month: str = "", end_month: str = "") -> dict:
    """Per bulan: jumlah kiriman, fill rate (qty dikirim / diminta), on-time rate, biaya kirim total dan per unit."""
    p = bq.period(start_month, end_month)
    sql = f"""
        select month, sum(shipments) as kiriman,
               safe_divide(sum(qty_shipped), sum(qty_requested)) as fill_rate,
               safe_divide(sum(on_time_shipments), sum(shipments)) as on_time_rate,
               sum(delivery_cost) as biaya_kirim,
               safe_divide(sum(delivery_cost), sum(qty_shipped)) as biaya_per_unit
        from {bq.table('mart_dc_store_monthly')}
        where month between @start and @end group by month order by month"""
    return {"periode": p["label"], "bulan": bq.query(sql, start=p["start"], end=p["end"])}


@safe
def dc_per_toko(urutan: str = "terendah", metric: str = "on_time_rate", limit: int = 10,
                start_month: str = "", end_month: str = "") -> dict:
    """Ranking toko tujuan kiriman DC. metric: on_time_rate | fill_rate | biaya_per_unit."""
    if metric not in {"on_time_rate", "fill_rate", "biaya_per_unit"}:
        raise ValueError("metric harus on_time_rate, fill_rate, atau biaya_per_unit")
    order = "asc" if (urutan or "").lower().startswith("terendah") else "desc"
    p = bq.period(start_month, end_month)
    sql = f"""
        select store_code, any_value(regency) as regency, sum(shipments) as kiriman,
               safe_divide(sum(qty_shipped), sum(qty_requested)) as fill_rate,
               safe_divide(sum(on_time_shipments), sum(shipments)) as on_time_rate,
               safe_divide(sum(delivery_cost), sum(qty_shipped)) as biaya_per_unit
        from {bq.table('mart_dc_store_monthly')}
        where month between @start and @end
        group by store_code order by {metric} {order} limit @lim"""
    rows = bq.query(sql, start=p["start"], end=p["end"], lim=max(1, min(int(limit), 50)))
    return {"periode": p["label"], "metric": metric, "toko": rows}


TOOLS = [tren_dc_bulanan, dc_per_kabupaten, dc_per_toko]
