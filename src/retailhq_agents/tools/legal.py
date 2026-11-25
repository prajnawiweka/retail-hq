"""Tool Legal: status kontrak sewa, izin, dan vendor."""
from __future__ import annotations

from retailhq_agents import bq
from retailhq_agents.tools.common import safe

T = "mart_contract_status"


@safe
def kontrak_jatuh_tempo(hari: int = 180, contract_type: str = "", store_code: str = "") -> dict:
    """Kontrak yang berakhir dalam `hari` ke depan (atau sudah berakhir), dihitung dari tanggal laporan
    2026-10-31. Tiap kontrak: jenis, toko, vendor, tanggal berakhir, sisa hari, nilai tahunan, dan nilai
    tahunan jika diperpanjang (sudah termasuk eskalasi). contract_type opsional (misal 'sewa')."""
    sql = f"""
        select contract_id, contract_type, store_code, store_name, regency, vendor_name,
               end_date, days_to_expiry, expiry_bucket, status,
               annual_value, escalation_pct, next_annual_value_if_renewed
        from {bq.table(T)}
        where days_to_expiry <= @hari
          and (@ctype = '' or lower(contract_type) like concat('%', lower(@ctype), '%'))
          and (@store = '' or store_code = @store)
        order by days_to_expiry
        limit 50"""
    rows = bq.query(sql, hari=int(hari), ctype=contract_type.strip(), store=store_code.strip().upper())
    return {"per_tanggal": "2026-10-31", "batas_hari": int(hari), "jumlah": len(rows), "kontrak": rows}


@safe
def ringkasan_kontrak() -> dict:
    """Jumlah dan nilai tahunan kontrak per jenis dan per kategori sisa waktu (sudah berakhir, <=90 hari,
    91-180 hari, >180 hari)."""
    sql = f"""
        select contract_type, expiry_bucket, count(*) as jumlah, sum(annual_value) as nilai_tahunan,
               sum(next_annual_value_if_renewed - annual_value) as tambahan_biaya_jika_diperpanjang
        from {bq.table(T)}
        group by 1, 2 order by 1, 2"""
    return {"per_tanggal": "2026-10-31", "ringkasan": bq.query(sql)}


TOOLS = [kontrak_jatuh_tempo, ringkasan_kontrak]
