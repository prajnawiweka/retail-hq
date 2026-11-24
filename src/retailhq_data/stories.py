"""Pola "tertanam" (planted insights) yang sengaja dimasukkan ke data dummy.

Tujuannya: agent punya temuan nyata untuk ditemukan, dan hasil analisa bisa dicek.
Daftar ini ditulis ke data/_answer_key.md. Jangan beri file itu ke agent.
"""
from __future__ import annotations

import pandas as pd


def pick_stories(stores: pd.DataFrame) -> dict:
    def first(mask):
        return stores.loc[mask, "store_code"].iloc[0]

    reg = stores["store_type"] == "reguler"
    old = stores["open_date"] < pd.Timestamp("2024-01-01")
    picked = {
        "competitor_store": first((stores["regency"] == "Denpasar") & (stores["location_type"] == "perumahan") & reg & old),
        "competitor_from": "2026-02-01",
        "shrink_store": first((stores["regency"] == "Badung") & (stores["location_type"] == "wisata") & old),
        "shrink_cashier": "KSR2",
        "bad_supplier": "SUP001",
        "bad_supplier_from": "2025-08-01",
        "bad_supplier_to": "2025-12-31",
        "bad_campaign": "CMP-2025-07",
        "energy_store": first((stores["regency"] == "Gianyar") & old),
        "it_store": first((stores["regency"] == "Tabanan") & old),
        "hr_store": first((stores["regency"] == "Denpasar") & (stores["location_type"] != "perumahan") & old),
        "weak_new_store": "BLL05",
        "loss_store": first((stores["regency"] == "Badung") & (stores["district"] == "Kuta Selatan") & old),
        "planogram_am": "I Wayan Darmawan",
    }
    codes = [v for k, v in picked.items() if k.endswith("_store")]
    assert len(codes) == len(set(codes)), f"toko cerita tumpang tindih: {codes}"
    return picked


def answer_key(s: dict) -> str:
    return f"""# Answer key — pola tertanam di data dummy

File ini untuk mengecek hasil analisa agent. JANGAN dimuat ke BigQuery atau diberikan ke agent.

| # | Department | Pola | Detail |
|---|---|---|---|
| 1 | Operation / Marketing | Kompetitor baru | Toko {s['competitor_store']} turun sekitar 18% mulai {s['competitor_from']}, achievement di bawah target |
| 2 | Loss Prevention | Shrinkage tinggi | Toko {s['shrink_store']}: selisih stock opname dan write-off "hilang" sekitar 3x rata-rata; kasir {s['shrink_store']}-{s['shrink_cashier']} void/refund dan selisih kas tinggi |
| 3 | Supply Chain / DC | Supplier bermasalah | {s['bad_supplier']} (Minuman) fill rate turun {s['bad_supplier_from']} s.d. {s['bad_supplier_to']}; OOS Minuman naik, penjualan Minuman turun |
| 4 | Marketing / Merchandise | Campaign rugi | {s['bad_campaign']} biaya besar, uplift hampir nol |
| 5 | ESG | Energi boros | Toko {s['energy_store']} kWh chiller sekitar 35% di atas toko sejenis (chiller lama) |
| 6 | IT | POS tua | Toko {s['it_store']}: POS tahun 2018, downtime dan tiket jauh di atas rata-rata |
| 7 | HR | Turnover & lembur | Toko {s['hr_store']}: turnover tinggi dan lembur besar |
| 8 | Store Dev | Toko baru lemah | {s['weak_new_store']} (buka 2025-10-10) SPD sekitar 55% dari rencana, payback panjang |
| 9 | Finance | EBITDA negatif | Toko {s['loss_store']}: sewa sekitar 12% dari sales, EBITDA negatif sepanjang periode |
| 10 | Merchandise / Operation | Kepatuhan planogram | Toko di bawah AM {s['planogram_am']} kepatuhan display sekitar 72% vs rata-rata sekitar 92% |
| 11 | Legal | Kontrak jatuh tempo | Beberapa kontrak sewa/izin berakhir Nov 2026 s.d. Mar 2027 (lihat dim_contract) |
"""
