"""Tool HR: headcount, turnover, lembur, produktivitas tenaga kerja."""
from __future__ import annotations

from retailhq_agents.tools.common import safe, store_ranking

METRICS = {
    "turnover_rate": "safe_divide(sum(exits), avg(headcount_end))",
    "overtime_ratio": "safe_divide(sum(overtime_hours), sum(hours_worked))",
    "sales_per_labor_hour": "safe_divide(sum(net_sales), sum(hours_worked) + sum(overtime_hours))",
    "labor_cost_pct": "safe_divide(sum(salary), sum(net_sales))",
    "headcount_rata2": "avg(headcount_end)",
    "karyawan_keluar": "sum(exits)",
    "jam_lembur": "sum(overtime_hours)",
}


@safe
def ranking_toko_hr(
    metric: str = "turnover_rate",
    urutan: str = "tertinggi",
    limit: int = 10,
    start_month: str = "",
    end_month: str = "",
    regency: str = "",
    am_name: str = "",
) -> dict:
    """Ranking toko untuk metrik HR, beserta rata-rata jaringan sebagai pembanding.

    metric: turnover_rate (karyawan keluar / rata-rata headcount, untuk seluruh periode) | overtime_ratio
    (jam lembur / jam kerja) | sales_per_labor_hour | labor_cost_pct (gaji / sales) | headcount_rata2 |
    karyawan_keluar | jam_lembur. urutan 'tertinggi' atau 'terendah'. Periode YYYY-MM, kosong = 12 bulan terakhir.
    """
    return store_ranking(METRICS, metric, urutan, limit, start_month, end_month, regency, am_name)


TOOLS = [ranking_toko_hr]
