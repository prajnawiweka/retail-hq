"""Tool Marketing & CRM: kinerja campaign dan member."""
from __future__ import annotations

from retailhq_agents import bq
from retailhq_agents.tools.common import safe


@safe
def kinerja_campaign(start_month: str = "", end_month: str = "", urutan: str = "terendah") -> dict:
    """Campaign yang berjalan di periode (overlap dengan rentang bulan), urut ROI 'terendah' atau 'tertinggi'.
    Uplift dihitung difference-in-differences terhadap baseline; ROI = (incremental gross profit - biaya) / biaya.
    Tiap campaign: kategori target, channel, tanggal, biaya, incremental sales, uplift, ROI."""
    p = bq.period(start_month, end_month)
    order = "asc" if (urutan or "").lower().startswith("terendah") else "desc"
    sql = f"""
        select campaign_id, campaign_name, target_category, channel, start_date, end_date, campaign_days,
               cost, sales_during, baseline_sales, incremental_sales, incremental_gross_profit, uplift_pct, roi
        from {bq.table('mart_campaign_performance')}
        where start_date <= last_day(@end) and end_date >= @start
        order by roi {order}"""
    rows = bq.query(sql, start=p["start"], end=p["end"])
    tot = {
        "jumlah_campaign": len(rows),
        "total_biaya": sum(r["cost"] or 0 for r in rows),
        "total_incremental_gross_profit": sum(r["incremental_gross_profit"] or 0 for r in rows),
        "campaign_roi_negatif": sum(1 for r in rows if (r["roi"] or 0) < 0),
    }
    return {"periode": p["label"], "total": tot, "campaign": rows}


@safe
def kinerja_member(start_month: str = "", end_month: str = "") -> dict:
    """Member per tipe (lokal/turis/ekspat) per bulan: member aktif, retensi dari bulan lalu, kunjungan,
    net sales, AMB member. Untuk melihat tren loyalitas."""
    p = bq.period(start_month, end_month)
    sql = f"""
        select month, member_type, active_members, retention_rate, visits, net_sales, amb_member
        from {bq.table('mart_member_monthly')}
        where month between @start and @end
        order by member_type, month"""
    return {"periode": p["label"], "bulan": bq.query(sql, start=p["start"], end=p["end"])}


TOOLS = [kinerja_campaign, kinerja_member]
