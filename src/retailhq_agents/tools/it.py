"""Tool IT: tiket gangguan, downtime POS, umur aset."""
from __future__ import annotations

from retailhq_agents import bq
from retailhq_agents.tools.common import safe, store_ranking

METRICS = {
    "it_tickets": "sum(it_tickets)",
    "pos_downtime_menit": "sum(pos_downtime_minutes)",
    "rata2_jam_penyelesaian": "safe_divide(sum(it_tickets * avg_resolution_hours), sum(it_tickets))",
    "it_cost": "sum(it_cost)",
}


@safe
def ranking_toko_it(
    metric: str = "pos_downtime_menit",
    urutan: str = "tertinggi",
    limit: int = 10,
    start_month: str = "",
    end_month: str = "",
    regency: str = "",
) -> dict:
    """Ranking toko untuk gangguan IT, beserta rata-rata jaringan.
    metric: it_tickets | pos_downtime_menit | rata2_jam_penyelesaian | it_cost."""
    return store_ranking(METRICS, metric, urutan, limit, start_month, end_month, regency)


@safe
def aset_it_toko(store_code: str = "", asset_type: str = "POS", limit: int = 10) -> dict:
    """Umur aset IT per toko (default POS): tahun pembelian tertua, rata-rata umur (tahun), jumlah unit.
    Tanpa store_code: daftar toko dengan aset tertua. asset_type: POS | printer | CCTV | jaringan."""
    sql = f"""
        select store_code, asset_type, count(*) as unit,
               min(purchase_date) as beli_tertua,
               round(avg(date_diff(date '2026-10-31', purchase_date, day)) / 365.25, 1) as rata2_umur_tahun
        from {bq.staging_table('stg_it_asset')}
        where (@store = '' or store_code = @store) and (@atype = '' or lower(asset_type) = lower(@atype))
        group by store_code, asset_type
        order by beli_tertua
        limit @lim"""
    rows = bq.query(sql, store=store_code.strip().upper(), atype=asset_type.strip(), lim=max(1, min(int(limit), 50)))
    return {"per_tanggal": "2026-10-31", "aset": rows}


TOOLS = [ranking_toko_it, aset_it_toko]
