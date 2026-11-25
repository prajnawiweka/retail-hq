"""Tool Loss Prevention: shrinkage stock opname, write-off, kas kasir, void/refund."""
from __future__ import annotations

from retailhq_agents import bq
from retailhq_agents.tools.common import safe, store_ranking

METRICS = {
    "opname_shrink_pct": "safe_divide(sum(opname_loss_value), sum(safe_divide(opname_loss_value, opname_shrink_pct)))",
    "selisih_opname": "sum(opname_loss_value)",
    "writeoff_hilang": "sum(writeoff_hilang_value)",
    "writeoff_hilang_pct": "safe_divide(sum(writeoff_hilang_value), sum(net_sales))",
    "writeoff_expired": "sum(writeoff_expired_value)",
    "refund_value": "sum(refund_value)",
    "void_value": "sum(void_value)",
    "cash_variance": "sum(cash_variance)",
    "hari_kas_kurang": "sum(cash_short_count)",
}


@safe
def ranking_toko_shrink(
    metric: str = "selisih_opname",
    urutan: str = "tertinggi",
    limit: int = 10,
    start_month: str = "",
    end_month: str = "",
    regency: str = "",
) -> dict:
    """Ranking toko untuk risiko kehilangan, beserta rata-rata jaringan.

    metric: opname_shrink_pct (selisih stock opname / nilai sistem) | selisih_opname (rupiah) |
    writeoff_hilang (barang hilang, rupiah) | writeoff_hilang_pct | writeoff_expired | refund_value |
    void_value | cash_variance (kas fisik - sistem, negatif = kurang) | hari_kas_kurang.
    Untuk cash_variance pakai urutan 'terendah' (paling minus).
    """
    return store_ranking(METRICS, metric, urutan, limit, start_month, end_month, regency)


@safe
def kasir_berisiko(store_code: str = "", limit: int = 10, start_month: str = "", end_month: str = "") -> dict:
    """Kasir (login POS) dengan void/refund per hari dan selisih kas terburuk, dibanding rata-rata semua kasir.
    store_code opsional untuk melihat kasir di satu toko. Urut skor risiko tertinggi."""
    p = bq.period(start_month, end_month)
    t = bq.table("mart_cashier_monthly")
    sql = f"""
        with k as (
          select cashier_id, any_value(store_code) as store_code,
                 sum(days) as hari, sum(void_count) as void_count, sum(refund_count) as refund_count,
                 sum(void_value) as void_value, sum(refund_value) as refund_value,
                 safe_divide(sum(void_count), sum(days)) as void_per_hari,
                 safe_divide(sum(refund_count), sum(days)) as refund_per_hari,
                 sum(cash_variance) as selisih_kas, sum(short_days) as hari_kas_kurang
          from {t} where month between @start and @end
          group by cashier_id),
        z as (
          select *,
                 (void_per_hari - avg(void_per_hari) over ()) / nullif(stddev(void_per_hari) over (), 0)
               + (refund_per_hari - avg(refund_per_hari) over ()) / nullif(stddev(refund_per_hari) over (), 0)
               - (selisih_kas - avg(selisih_kas) over ()) / nullif(stddev(selisih_kas) over (), 0) as skor_risiko
          from k)
        select * from z where (@store = '' or store_code = @store)
        order by skor_risiko desc limit @lim"""
    avg = bq.query(
        f"""select safe_divide(sum(void_count), sum(days)) as void_per_hari,
                   safe_divide(sum(refund_count), sum(days)) as refund_per_hari,
                   safe_divide(sum(cash_variance), count(distinct cashier_id)) as selisih_kas_per_kasir
            from {t} where month between @start and @end""",
        start=p["start"], end=p["end"],
    )[0]
    rows = bq.query(sql, start=p["start"], end=p["end"], store=store_code.strip().upper(),
                    lim=max(1, min(int(limit), 30)))
    return {"periode": p["label"], "rata_rata_semua_kasir": avg, "kasir": rows,
            "catatan": "skor_risiko = gabungan z-score void, refund, dan selisih kas; makin tinggi makin janggal"}


TOOLS = [ranking_toko_shrink, kasir_berisiko]
