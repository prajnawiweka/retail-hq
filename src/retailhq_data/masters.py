"""Master data: toko, produk, supplier.

Semua nama toko, merek, supplier, dan orang adalah fiktif.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

REGENCY_CODE = {
    "Denpasar": "DPS", "Badung": "BDG", "Gianyar": "GIA", "Tabanan": "TBN",
    "Buleleng": "BLL", "Klungkung": "KLK", "Karangasem": "KRA", "Bangli": "BGL",
}

# kecamatan -> bobot tipe lokasi (wisata, perumahan, jalan utama, dekat kampus)
DISTRICTS = {
    "Denpasar": {"Denpasar Selatan": (.35, .35, .2, .1), "Denpasar Timur": (.05, .5, .3, .15),
                 "Denpasar Barat": (.05, .45, .3, .2), "Denpasar Utara": (.05, .5, .25, .2)},
    "Badung": {"Kuta": (.8, .05, .15, 0), "Kuta Utara": (.6, .2, .2, 0), "Kuta Selatan": (.55, .15, .15, .15),
               "Mengwi": (.05, .55, .4, 0), "Abiansemal": (0, .6, .4, 0)},
    "Gianyar": {"Ubud": (.85, .05, .1, 0), "Sukawati": (.2, .4, .4, 0), "Gianyar": (0, .5, .5, 0),
                "Blahbatuh": (0, .6, .4, 0)},
    "Tabanan": {"Tabanan": (0, .5, .4, .1), "Kediri": (.3, .4, .3, 0), "Marga": (0, .6, .4, 0)},
    "Buleleng": {"Buleleng": (.15, .35, .3, .2), "Sukasada": (0, .5, .3, .2), "Seririt": (.1, .5, .4, 0)},
    "Klungkung": {"Klungkung": (.1, .5, .4, 0)},
    "Karangasem": {"Karangasem": (.2, .5, .3, 0), "Manggis": (.5, .2, .3, 0)},
    "Bangli": {"Bangli": (.1, .5, .4, 0)},
}
LOC_TYPES = ["wisata", "perumahan", "jalan utama", "dekat kampus"]
DIST_KM = {"Denpasar": 6, "Badung": 18, "Gianyar": 25, "Tabanan": 28, "Buleleng": 85,
           "Klungkung": 40, "Karangasem": 70, "Bangli": 45}

AM_NAMES = ["I Made Suardana", "Ni Kadek Ayu Lestari", "I Wayan Darmawan", "Putu Rina Andayani",
            "I Komang Budiarta", "Ni Luh Sri Wahyuni", "I Ketut Arsana"]
AK_NAMES = ["Gede Pradnyana", "Ni Nyoman Sukerti", "Kadek Hendra Wijaya"]

# kategori: (jumlah SKU, subkategori, margin kotor rata-rata, rentang harga jual)
CATEGORIES = {
    "Minuman": (45, ["Air Mineral", "Minuman Ringan", "Teh & Kopi Siap Minum", "Minuman Isotonik", "Jus"], .24, (4000, 18000)),
    "Makanan Ringan": (45, ["Keripik", "Biskuit", "Cokelat & Permen", "Kacang"], .26, (2500, 25000)),
    "Mie & Makanan Instan": (20, ["Mie Instan", "Makanan Kaleng", "Bumbu Instan"], .14, (3000, 22000)),
    "Susu & Olahan": (20, ["Susu UHT", "Yogurt", "Keju & Mentega"], .18, (5000, 45000)),
    "Roti & Kue": (15, ["Roti Tawar", "Roti Isi", "Kue Basah"], .30, (5000, 25000)),
    "Makanan Siap Saji": (15, ["Nasi Bungkus", "Gorengan", "Sandwich", "Kopi Seduh"], .45, (8000, 35000)),
    "Frozen": (15, ["Nugget & Sosis", "Es Krim", "Frozen Snack"], .25, (8000, 55000)),
    "Bahan Pokok": (25, ["Beras", "Minyak Goreng", "Gula", "Telur", "Tepung"], .09, (12000, 80000)),
    "Kebutuhan Rumah Tangga": (25, ["Sabun Cuci", "Pembersih Lantai", "Tisu", "Pengharum"], .20, (6000, 45000)),
    "Perawatan Diri": (30, ["Sabun Mandi", "Sampo", "Pasta Gigi", "Sunscreen", "Deodoran"], .24, (5000, 95000)),
    "Rokok": (15, ["Kretek", "Putih"], .07, (22000, 40000)),
    "Bayi": (10, ["Popok", "Susu Formula", "Tisu Basah Bayi"], .16, (15000, 120000)),
    "Kebutuhan Upacara": (15, ["Canang & Bunga", "Dupa", "Kain & Perlengkapan", "Buah Banten"], .32, (3000, 35000)),
    "Es Batu & Lainnya": (5, ["Es Batu", "Pulsa Fisik"], .20, (5000, 25000)),
}
BRAND_POOL = ["Segar", "Tirta", "Kriuk", "Gurih", "Manis", "Rasa", "Pulau", "Dewata", "Sari", "Nusa",
              "Mekar", "Lestari", "Bening", "Sejuk", "Harum", "Bersih", "Prima", "Jaya", "Murni", "Surya"]
SIZES = ["kecil", "sedang", "besar", "hemat", "jumbo"]

SUPPLIER_NAMES = ["PT Tirta Dewata Distribusi", "PT Sumber Pangan Nusantara", "CV Segar Abadi", "PT Bali Niaga Utama",
                  "PT Karya Snack Indonesia", "CV Mekar Sari", "PT Susu Pulau Dewata", "PT Roti Harum Bali",
                  "CV Dapur Siap Saji", "PT Beku Prima Logistik", "PT Pangan Pokok Jaya", "CV Beras Subak",
                  "PT Bersih Rumah Sentosa", "PT Rawat Diri Lestari", "PT Tembakau Nusa", "PT Bunda Ceria",
                  "CV Upakara Bali Mandiri", "UD Canang Sari Denpasar", "PT Es Kristal Bali", "PT Minuman Surya",
                  "CV Kacang Gurih", "PT Kopi Kintamani Jaya", "PT Distribusi Timur Bali", "CV Sinar Buleleng",
                  "PT Logistik Gilimanuk"]


def make_stores(cfg: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    n = 0
    for regency, count in cfg["stores_per_regency"].items():
        districts = list(DISTRICTS[regency].items())
        for i in range(count):
            n += 1
            dname, w = districts[i % len(districts)]
            loc = rng.choice(LOC_TYPES, p=np.array(w) / sum(w))
            rows.append({"store_code": f"{REGENCY_CODE[regency]}{i + 1:02d}", "regency": regency, "district": dname,
                         "location_type": loc})
    s = pd.DataFrame(rows)
    s["store_name"] = "RH " + s["district"] + " " + s.groupby("district").cumcount().add(1).astype(str).str.zfill(2)

    # QSR di toko wisata/kampus besar
    qsr_pool = s.index[s["location_type"].isin(["wisata", "dekat kampus"])]
    qsr = rng.choice(qsr_pool, size=min(8, len(qsr_pool)), replace=False)
    s["store_type"] = "reguler"
    s.loc[qsr, "store_type"] = "QSR"
    s["size_m2"] = np.where(s["store_type"] == "QSR", rng.integers(180, 260, len(s)), rng.integers(110, 210, len(s)))

    # AM: urut geografis, 7 AM (6-8 toko); AK: 3 AK membawahi AM
    am_idx = np.minimum(np.arange(len(s)) * len(AM_NAMES) // len(s), len(AM_NAMES) - 1)
    s["am_name"] = [AM_NAMES[i] for i in am_idx]
    s["ak_name"] = [AK_NAMES[min(i * len(AK_NAMES) // len(AM_NAMES), 2)] for i in am_idx]

    # Tanggal buka: mayoritas sebelum periode; 4 toko baru dibuka dalam periode
    s["open_date"] = pd.to_datetime("2015-01-01") + pd.to_timedelta(rng.integers(0, 3300, len(s)), unit="D")
    new_codes = ["BDG14", "GIA07", "BLL05", "DPS14"]
    new_dates = ["2025-02-15", "2025-06-20", "2025-10-10", "2026-04-18"]
    for c, dte in zip(new_codes, new_dates):
        s.loc[s["store_code"] == c, "open_date"] = pd.Timestamp(dte)
    s["status"] = "aktif"
    s["dist_km_dc"] = s["regency"].map(DIST_KM) + rng.integers(-4, 8, len(s))
    s["dist_km_dc"] = s["dist_km_dc"].clip(lower=2)

    # Skala penjualan dasar (SPD rupiah) per toko
    loc_base = {"wisata": 13_500_000, "perumahan": 9_000_000, "jalan utama": 10_500_000, "dekat kampus": 9_500_000}
    s["base_spd"] = s["location_type"].map(loc_base) * (s["size_m2"] / 160) ** 0.5 * rng.lognormal(0, .18, len(s))
    s.loc[s["store_type"] == "QSR", "base_spd"] *= 1.2
    s["growth_yoy"] = rng.normal(.06, .05, len(s))
    s["amb_base"] = s["location_type"].map({"wisata": 68000, "perumahan": 47000, "jalan utama": 52000,
                                            "dekat kampus": 38000}) * rng.lognormal(0, .08, len(s))
    return s


def make_suppliers(rng: np.random.Generator) -> pd.DataFrame:
    n = len(SUPPLIER_NAMES)
    return pd.DataFrame({
        "supplier_id": [f"SUP{i + 1:03d}" for i in range(n)],
        "supplier_name": SUPPLIER_NAMES,
        "lead_time_days": rng.integers(2, 9, n),
        "payment_terms": rng.choice(["COD", "14 hari", "30 hari", "45 hari"], n, p=[.1, .3, .45, .15]),
    })


def make_products(cfg: dict, rng: np.random.Generator, suppliers: pd.DataFrame) -> pd.DataFrame:
    rows = []
    sup_ids = suppliers["supplier_id"].tolist()
    k = 0
    for ci, (cat, (n, subs, margin, (lo, hi))) in enumerate(CATEGORIES.items()):
        cat_sups = [sup_ids[(ci * 2 + j) % len(sup_ids)] for j in range(2)]
        for i in range(n):
            k += 1
            sub = subs[i % len(subs)]
            brand = BRAND_POOL[rng.integers(len(BRAND_POOL))]
            price = float(np.round(np.exp(rng.uniform(np.log(lo), np.log(hi))) / 500) * 500)
            m = float(np.clip(rng.normal(margin + .045, .04), .05, .6))
            rows.append({
                "sku": f"SKU{k:04d}", "product_name": f"{brand} {sub} {SIZES[i % len(SIZES)]}",
                "category": cat, "subcategory": sub, "brand": brand,
                "supplier_id": cat_sups[i % 2] if cat != "Kebutuhan Upacara" else sup_ids[16 + i % 2],
                "cost_price": round(price * (1 - m)), "sell_price": price,
            })
    p = pd.DataFrame(rows)
    # Popularitas dalam kategori (pola Pareto)
    p["popularity"] = rng.pareto(1.6, len(p)) + .2
    return p
