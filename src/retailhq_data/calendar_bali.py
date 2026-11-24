"""Kalender harian dengan faktor musiman Bali.

Tanggal hari raya diambil dari SE Gubernur Bali / Kemenag (dicek Nov 2026).
Faktor (multiplier) adalah asumsi data dummy, bukan data riil.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NYEPI = ["2025-03-29", "2026-03-19"]
GALUNGAN = ["2025-04-23", "2025-11-19", "2026-06-17"]  # Kuningan = Galungan + 10 hari
LEBARAN = ["2025-03-31", "2026-03-20"]


def build_calendar(start: str, end: str) -> pd.DataFrame:
    d = pd.DataFrame({"date": pd.date_range(start, end, freq="D")})
    d["dow"] = d["date"].dt.dayofweek  # 0 = Senin
    d["month"] = d["date"].dt.month
    d["day"] = d["date"].dt.day
    d["week_start"] = d["date"] - pd.to_timedelta(d["dow"], unit="D")
    d["month_start"] = d["date"].values.astype("datetime64[M]")

    dow_f = np.array([0.95, 0.94, 0.96, 0.98, 1.05, 1.12, 1.08])
    d["f_dow"] = dow_f[d["dow"]]

    # Gajian: tgl 25 s.d. 3 bulan berikutnya
    d["f_payday"] = np.where((d["day"] >= 25) | (d["day"] <= 3), 1.05, 1.0)

    d["is_nyepi"] = False
    d["f_event"] = 1.0          # efek umum semua toko
    d["f_upakara"] = 1.0        # efek tambahan kategori Kebutuhan Upacara
    d["event"] = ""

    def bump(day, factor, label, upakara=1.0):
        m = d["date"] == pd.Timestamp(day)
        d.loc[m, "f_event"] *= factor
        d.loc[m, "f_upakara"] *= upakara
        d.loc[m, "event"] = label

    for n in NYEPI:
        t = pd.Timestamp(n)
        d.loc[d["date"] == t, "is_nyepi"] = True
        d.loc[d["date"] == t, "event"] = "Nyepi (toko tutup)"
        bump(t - pd.Timedelta(days=2), 1.15, "Nyepi H-2", 1.6)
        bump(t - pd.Timedelta(days=1), 1.40, "Nyepi H-1 (Tawur Kesanga)", 2.2)
        bump(t + pd.Timedelta(days=1), 0.85, "Ngembak Geni")

    for g in GALUNGAN:
        t = pd.Timestamp(g)
        bump(t - pd.Timedelta(days=3), 1.08, "Penyekeban Galungan", 1.8)
        bump(t - pd.Timedelta(days=2), 1.15, "Penyajaan Galungan", 2.5)
        bump(t - pd.Timedelta(days=1), 1.28, "Penampahan Galungan", 3.0)
        bump(t, 0.92, "Galungan", 1.5)
        bump(t + pd.Timedelta(days=1), 1.05, "Umanis Galungan", 1.2)
        k = t + pd.Timedelta(days=10)
        bump(k - pd.Timedelta(days=1), 1.12, "Penampahan Kuningan", 2.2)
        bump(k, 1.05, "Kuningan", 1.5)

    d["f_lebaran"] = 1.0  # diterapkan ke toko perumahan/kampus (pekerja mudik)
    for l in LEBARAN:
        t = pd.Timestamp(l)
        m = (d["date"] >= t - pd.Timedelta(days=3)) & (d["date"] <= t + pd.Timedelta(days=5))
        d.loc[m, "f_lebaran"] = 0.90

    # High season wisata: Jul-Agu dan 15 Des - 5 Jan (berlaku penuh di toko wisata)
    hs = d["month"].isin([7, 8]) | ((d["month"] == 12) & (d["day"] >= 15)) | ((d["month"] == 1) & (d["day"] <= 5))
    d["f_high_season"] = np.where(hs, 1.0, 0.0)
    d.loc[(d["month"] == 12) & (d["day"].isin([24, 25, 31])), "f_event"] *= 1.06
    return d
