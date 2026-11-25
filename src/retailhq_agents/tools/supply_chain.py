"""Tool Supply Chain & DC: OOS, SOH 0, fill rate supplier, pengiriman DC."""
from __future__ import annotations

from retailhq_agents import bq
from retailhq_agents.tools.common import STORE_FILTER, params, safe, scope

SM = "mart_store_monthly"


@safe
def ringkasan_supply_chain(start_month: str = "", end_month: str = "", regency: str = "") -> dict:
    """Ringkasan Supply Chain (bulan YYYY-MM; kosong = 12 bulan terakhir): OOS rate dan SOH 0 rate toko
    (dibanding tahun lalu), fill rate dan on-time supplier, fill rate, on-time, dan biaya per unit DC.
    OOS = SKU ditandai out of stock; SOH 0 = stok sistem nol. Keduanya tidak sama."""
    p = bq.period(start_month, end_month)
    q = params(p, regency)
    stock = bq.query(
        f"""select
              safe_divide(sum(if(month between @start and @end, oos_sku_weeks, 0)), sum(if(month between @start and @end, sku_weeks, 0))) as oos_rate,
              safe_divide(sum(if(month between @start and @end, soh_zero_sku_weeks, 0)), sum(if(month between @start and @end, sku_weeks, 0))) as soh0_rate,
              safe_divide(sum(if(month between @py_start and @py_end, oos_sku_weeks, 0)), sum(if(month between @py_start and @py_end, sku_weeks, 0))) as oos_rate_tahun_lalu,
              safe_divide(sum(if(month between @py_start and @py_end, soh_zero_sku_weeks, 0)), sum(if(month between @py_start and @py_end, sku_weeks, 0))) as soh0_rate_tahun_lalu
            from {bq.table(SM)} where {STORE_FILTER}""",
        **q,
    )[0]
    sup = bq.query(
        f"""select safe_divide(sum(qty_received), sum(qty_ordered)) as fill_rate_supplier,
                   safe_divide(sum(on_time_lines), sum(po_lines)) as on_time_supplier
            from {bq.table('mart_supplier_monthly')} where month between @start and @end""",
        **q,
    )[0]
    dc = bq.query(
        f"""select safe_divide(sum(qty_shipped), sum(qty_requested)) as fill_rate_dc,
                   safe_divide(sum(on_time_shipments), sum(shipments)) as on_time_dc,
                   safe_divide(sum(delivery_cost), sum(qty_shipped)) as biaya_kirim_per_unit
            from {bq.table('mart_dc_store_monthly')} where month between @start and @end and {STORE_FILTER}""",
        **q,
    )[0]
    return {**scope(p, regency), "stok_toko": stock, "supplier": sup, "dc": dc,
            "catatan": "fill rate supplier tidak terpengaruh filter kabupaten"}


@safe
def kinerja_supplier(start_month: str = "", end_month: str = "", hanya_bermasalah: bool = False) -> dict:
    """Per supplier: fill rate, on-time rate, rata-rata keterlambatan, fill rate bulanan terendah dan
    bulannya, serta jumlah bulan fill rate < 90%. Urut fill rate terendah.
    hanya_bermasalah=True hanya menampilkan supplier yang pernah < 90% dalam periode."""
    p = bq.period(start_month, end_month)
    sql = f"""
        with m as (
          select supplier_id, supplier_name, month,
                 safe_divide(qty_received, qty_ordered) as fr, qty_received, qty_ordered,
                 on_time_lines, po_lines
          from {bq.table('mart_supplier_monthly')} where month between @start and @end)
        select supplier_id, any_value(supplier_name) as supplier_name,
               safe_divide(sum(qty_received), sum(qty_ordered)) as fill_rate,
               safe_divide(sum(on_time_lines), sum(po_lines)) as on_time_rate,
               min(fr) as fill_rate_bulan_terendah,
               array_agg(format_date('%Y-%m', month) order by fr limit 1)[offset(0)] as bulan_terendah,
               countif(fr < 0.9) as bulan_di_bawah_90,
               string_agg(if(fr < 0.9, format_date('%Y-%m', month), null), ', ' order by month) as daftar_bulan_di_bawah_90
        from m group by supplier_id
        having not @only_bad or countif(fr < 0.9) > 0
        order by fill_rate"""
    rows = bq.query(sql, **params(p, only_bad=bool(hanya_bermasalah)))
    return {"periode": p["label"], "supplier": rows[:25]}


@safe
def top_sku_oos(limit: int = 15, start_month: str = "", end_month: str = "", supplier_id: str = "") -> dict:
    """SKU yang paling banyak membuat toko OOS: jumlah toko OOS maksimum dalam satu bulan, toko SOH 0,
    estimasi lost sales, kategori, dan supplier. Filter opsional supplier_id (misal 'SUP001')."""
    p = bq.period(start_month, end_month)
    sql = f"""
        select sku, any_value(product_name) as product_name, any_value(category) as category,
               any_value(supplier_id) as supplier_id,
               max(stores_oos) as toko_oos_maks, max(stores_soh_zero) as toko_soh0_maks,
               sum(est_lost_sales) as est_lost_sales,
               countif(stores_oos > 0) as bulan_ada_oos
        from {bq.table('mart_oos_sku_monthly')}
        where month between @start and @end and (@sup = '' or supplier_id = @sup)
        group by sku
        order by toko_oos_maks desc, est_lost_sales desc
        limit @lim"""
    rows = bq.query(sql, **params(p, sup=supplier_id.strip().upper(), lim=max(1, min(int(limit), 50))))
    by_sup = bq.query(
        f"""select supplier_id, sum(est_lost_sales) as est_lost_sales, count(distinct sku) as sku_oos
            from {bq.table('mart_oos_sku_monthly')}
            where month between @start and @end and stores_oos > 0
            group by supplier_id order by est_lost_sales desc limit 5""",
        **params(p),
    )
    return {"periode": p["label"], "sku": rows, "lost_sales_per_supplier_top5": by_sup}


@safe
def tren_stok_bulanan(start_month: str = "", end_month: str = "", regency: str = "") -> dict:
    """Per bulan: OOS rate dan SOH 0 rate toko, fill rate semua supplier, serta supplier dengan fill rate
    terendah di bulan itu. Untuk melihat kapan masalah stok dimulai dan berakhir."""
    p = bq.period(start_month, end_month)
    sql = f"""
        with s as (
          select month, safe_divide(sum(oos_sku_weeks), sum(sku_weeks)) as oos_rate,
                 safe_divide(sum(soh_zero_sku_weeks), sum(sku_weeks)) as soh0_rate
          from {bq.table(SM)} where month between @start and @end and {STORE_FILTER} group by month),
        f as (
          select month, safe_divide(sum(qty_received), sum(qty_ordered)) as fill_rate_semua_supplier,
                 array_agg(struct(supplier_id, safe_divide(qty_received, qty_ordered) as fr)
                           order by safe_divide(qty_received, qty_ordered) limit 1)[offset(0)] as w
          from {bq.table('mart_supplier_monthly')} where month between @start and @end group by month)
        select s.*, f.fill_rate_semua_supplier,
               f.w.supplier_id as supplier_terendah, f.w.fr as fill_rate_supplier_terendah
        from s left join f using (month) order by month"""
    return {**scope(p, regency), "bulan": bq.query(sql, **params(p, regency))}


@safe
def dc_per_kabupaten(start_month: str = "", end_month: str = "") -> dict:
    """Kinerja pengiriman DC ke toko per kabupaten: fill rate, on-time rate, biaya kirim per unit, jumlah kiriman."""
    p = bq.period(start_month, end_month)
    sql = f"""
        select regency, count(distinct store_code) as toko, sum(shipments) as kiriman,
               safe_divide(sum(qty_shipped), sum(qty_requested)) as fill_rate,
               safe_divide(sum(on_time_shipments), sum(shipments)) as on_time_rate,
               safe_divide(sum(delivery_cost), sum(qty_shipped)) as biaya_per_unit
        from {bq.table('mart_dc_store_monthly')}
        where month between @start and @end
        group by regency order by on_time_rate"""
    return {"periode": p["label"], "kabupaten": bq.query(sql, **params(p))}


TOOLS = [ringkasan_supply_chain, kinerja_supplier, top_sku_oos, tren_stok_bulanan, dc_per_kabupaten]
