"""Tool ESG: energi, sampah dan daur ulang, kantong plastik."""
from __future__ import annotations

from retailhq_agents import bq
from retailhq_agents.tools.common import STORE_FILTER, params, safe, scope, store_ranking

METRICS = {
    "kwh_per_m2": "safe_divide(sum(kwh_total), any_value(size_m2) * count(*))",
    "kwh_ac_per_m2": "safe_divide(sum(kwh_ac), any_value(size_m2) * count(*))",
    "kwh_total": "sum(kwh_total)",
    "energy_cost_pct": "safe_divide(sum(energy_cost_pct * net_sales), sum(net_sales))",
    "recycle_rate": "safe_divide(sum(recycled_kg), sum(general_waste_kg) + sum(food_waste_kg))",
    "food_waste_kg": "sum(food_waste_kg)",
    "kantong_plastik_dipakai": "sum(plastic_bags_used)",
    "tas_guna_ulang_terjual": "sum(plastic_bags_sold)",
}


@safe
def ranking_toko_esg(
    metric: str = "kwh_per_m2",
    urutan: str = "tertinggi",
    limit: int = 10,
    start_month: str = "",
    end_month: str = "",
    regency: str = "",
) -> dict:
    """Ranking toko untuk metrik lingkungan, beserta rata-rata jaringan dan selisih terhadap toko sejenis
    (store_type sama). Energi dinormalisasi per m2 per bulan supaya toko besar dan kecil sebanding.

    Untuk pertanyaan soal chiller/pendingin JANGAN pakai tool ini, pakai efisiensi_chiller.
    metric: kwh_per_m2 | kwh_ac_per_m2 | kwh_total | energy_cost_pct |
    recycle_rate | food_waste_kg | kantong_plastik_dipakai (kantong kecil untuk curah/fresh) |
    tas_guna_ulang_terjual. Bali membatasi kantong plastik sekali pakai.
    """
    return store_ranking(METRICS, metric, urutan, limit, start_month, end_month, regency, peer_by="store_type")


@safe
def efisiensi_chiller(limit: int = 10, start_month: str = "", end_month: str = "", regency: str = "") -> dict:
    """WAJIB dipakai untuk pertanyaan chiller/pendingin/kulkas boros. kWh chiller per unit chiller per hari buka, per toko, dibanding rata-rata toko sejenis (store_type sama)
    dan rata-rata jaringan. Ini ukuran paling adil untuk mendeteksi chiller boros/tua, karena konsumsi chiller
    bergantung pada jumlah unit, bukan luas toko. Urut paling boros."""
    p = bq.period(start_month, end_month)
    sql = f"""
        with u as (
          select store_code, countif(fixture_type = 'chiller') as unit_chiller
          from {bq.staging_table('stg_fixture')} group by store_code),
        e as (
          select store_code, any_value(store_type) as store_type, any_value(regency) as regency,
                 sum(kwh_chiller) as kwh_chiller, sum(open_days) as hari_buka
          from {bq.table('mart_store_monthly')}
          where month between @start and @end and {STORE_FILTER}
          group by store_code),
        j as (
          select e.*, u.unit_chiller,
                 safe_divide(e.kwh_chiller, u.unit_chiller * e.hari_buka) as kwh_per_unit_per_hari
          from e join u using (store_code))
        select *,
               safe_divide(kwh_per_unit_per_hari, avg(kwh_per_unit_per_hari) over (partition by store_type)) - 1
                 as vs_toko_sejenis,
               safe_divide(kwh_per_unit_per_hari, avg(kwh_per_unit_per_hari) over ()) - 1 as vs_jaringan
        from j order by vs_toko_sejenis desc limit @lim"""
    rows = bq.query(sql, **params(p, regency, lim=max(1, min(int(limit), 50))))
    return {**scope(p, regency), "toko": rows}


TOOLS = [efisiensi_chiller, ranking_toko_esg]
