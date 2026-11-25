"""Tool Store Development: proyek capex, kinerja toko baru, payback."""
from __future__ import annotations

from retailhq_agents import bq
from retailhq_agents.tools.common import safe


@safe
def proyek_capex(project_type: str = "") -> dict:
    """Semua proyek capex (toko baru, renovasi, dll.): toko, jenis, nilai capex, tanggal buka, bulan beroperasi,
    rata-rata SPD, rata-rata achievement, rata-rata EBITDA bulanan, dan payback (bulan; kosong kalau EBITDA
    rata-rata negatif atau bukan toko baru). project_type opsional, misal 'baru'."""
    sql = f"""
        select project_id, store_code, store_name, regency, location_type, project_type, status,
               capex_amount, open_date, months_open, avg_spd, avg_achievement, avg_monthly_ebitda,
               payback_months
        from {bq.table('mart_store_dev')}
        where (@ptype = '' or lower(project_type) = lower(@ptype))
        order by open_date desc"""
    rows = bq.query(sql, ptype=project_type.strip())
    bench = bq.query(
        f"""select safe_divide(sum(net_sales), sum(open_days)) as spd_rata2_jaringan,
                   safe_divide(sum(net_sales), sum(target_sales)) as achievement_jaringan
            from {bq.table('mart_store_monthly')}
            where month > date_sub((select max(month) from {bq.table('mart_store_monthly')}), interval 12 month)""",
    )[0]
    return {"proyek": rows, "pembanding_12_bulan_terakhir": bench}


TOOLS = [proyek_capex]
