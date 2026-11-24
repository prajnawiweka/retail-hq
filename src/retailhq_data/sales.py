"""Penjualan: campaign, fact_sales_daily, fact_sales_category_daily, fact_sales_sku_weekly, fact_stock_weekly.

Penjualan dibangun dari bawah (toko x hari x kategori), lalu dijumlah ke toko x hari,
sehingga total kategori selalu sama persis dengan total toko.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .masters import CATEGORIES

CATS = list(CATEGORIES)
BASE_SHARE = {"Minuman": 18, "Makanan Ringan": 14, "Mie & Makanan Instan": 7, "Susu & Olahan": 7,
              "Roti & Kue": 4, "Makanan Siap Saji": 0, "Frozen": 4, "Bahan Pokok": 10,
              "Kebutuhan Rumah Tangga": 7, "Perawatan Diri": 8, "Rokok": 12, "Bayi": 3,
              "Kebutuhan Upacara": 3, "Es Batu & Lainnya": 3}
LOC_ADJ = {
    "wisata": {"Minuman": 1.35, "Perawatan Diri": 1.3, "Rokok": 1.1, "Bahan Pokok": .4, "Bayi": .5,
               "Kebutuhan Rumah Tangga": .6, "Es Batu & Lainnya": 1.5, "Kebutuhan Upacara": .6},
    "perumahan": {"Bahan Pokok": 1.4, "Kebutuhan Rumah Tangga": 1.3, "Bayi": 1.4, "Kebutuhan Upacara": 1.3},
    "dekat kampus": {"Mie & Makanan Instan": 1.6, "Makanan Ringan": 1.2, "Minuman": 1.1, "Bahan Pokok": .6,
                     "Bayi": .4, "Rokok": 1.2},
    "jalan utama": {"Rokok": 1.15, "Minuman": 1.1},
}
HS_UPLIFT = {"wisata": .25, "jalan utama": .08, "perumahan": .03, "dekat kampus": -.05}
CHANNELS = ["Instagram", "TikTok", "WhatsApp Blast", "Brosur", "In-store", "Member App"]


def make_campaigns(rng, stores, start, end) -> pd.DataFrame:
    rows = []
    months = pd.date_range(start, end, freq="MS")
    promo_cats = [c for c in CATS if c not in ("Rokok", "Makanan Siap Saji")]
    for m in months:
        for j in range(2 if m.month in (3, 6, 7, 11, 12) else 1):
            sd = m + pd.Timedelta(days=int(rng.integers(0, 15)))
            ed = sd + pd.Timedelta(days=int(rng.integers(7, 28)))
            local = rng.random() < .3
            cid = f"CMP-{m.year}-{m.month:02d}" + ("" if j == 0 else "B")
            cat = rng.choice(promo_cats)
            rows.append({
                "campaign_id": cid,
                "campaign_name": f"Promo {cat} {m.strftime('%b %Y')}" + (" (lokal)" if local else ""),
                "channel": rng.choice(CHANNELS), "start_date": sd, "end_date": min(ed, pd.Timestamp(end)),
                "cost": int(round(rng.uniform(4e6, 3e7) if not local else rng.uniform(1e6, 6e6), -5)),
                "target_category": cat,
                "target_store_code": rng.choice(stores["store_code"]) if local else None,
                "uplift": float(rng.uniform(.06, .22)),
            })
    c = pd.DataFrame(rows)
    bad = c["campaign_id"] == "CMP-2025-07"
    c.loc[bad, ["cost", "uplift", "target_store_code", "channel", "target_category"]] = [85_000_000, .005, None, "TikTok", "Minuman"]
    c.loc[bad, "campaign_name"] = "Promo Musim Liburan Jul 2025"
    return c


def _round_to_total(values: pd.Series, totals: pd.Series, keys: list[pd.Series]) -> np.ndarray:
    """Bulatkan ke rupiah utuh dan pastikan jumlah per grup sama dengan total grup."""
    r = np.round(values.to_numpy()).astype(np.int64)
    df = pd.DataFrame({"r": r, "t": totals.to_numpy()})
    for i, k in enumerate(keys):
        df[f"k{i}"] = k.to_numpy()
    kcols = [f"k{i}" for i in range(len(keys))]
    diff = df["t"] - df.groupby(kcols)["r"].transform("sum")
    first = ~df.duplicated(kcols)
    r[first.to_numpy()] += diff[first].to_numpy().astype(np.int64)
    return r


def simulate_sales(cfg, rng, cal, stores, products, campaigns, s) -> dict[str, pd.DataFrame]:
    start = pd.Timestamp(cfg["start_date"])
    # ---- toko x hari
    g = stores.merge(cal, how="cross")
    g = g[(g["date"] >= g["open_date"]) & (~g["is_nyepi"])].reset_index(drop=True)
    years = (g["date"] - start).dt.days / 365.25
    hs = g["f_high_season"] * g["location_type"].map(HS_UPLIFT)
    leb = np.where(g["location_type"].isin(["perumahan", "dekat kampus"]), g["f_lebaran"], 1.0)
    days_open = (g["date"] - g["open_date"]).dt.days
    ramp = np.clip(.65 + .35 * days_open / 180, .65, 1.0)
    core = g["base_spd"] * (1 + g["growth_yoy"]) ** years * (1 + hs) * leb * ramp
    g["core"] = core * g["f_dow"]  # dasar target (tanpa noise/cerita/event)

    story = np.ones(len(g))
    story[((g["store_code"] == s["competitor_store"]) & (g["date"] >= s["competitor_from"])).to_numpy()] = .82
    story[(g["store_code"] == s["weak_new_store"]).to_numpy()] = .55
    g["expected"] = g["core"] * g["f_payday"] * g["f_event"] * story * rng.lognormal(0, .07, len(g))

    # ---- toko x hari x kategori
    share = pd.DataFrame([{c: BASE_SHARE[c] * LOC_ADJ.get(lt, {}).get(c, 1.0) for c in CATS}
                          for lt in stores["location_type"]], index=stores["store_code"])
    share.loc[stores.loc[stores["store_type"] == "QSR", "store_code"], "Makanan Siap Saji"] = 12
    share = share.div(share.sum(axis=1), axis=0)
    cs = share.stack().rename("share").reset_index()
    cs.columns = ["store_code", "category", "share"]
    gc = g[["store_code", "date", "week_start", "month_start", "expected", "f_upakara"]].merge(cs, on="store_code")
    gc = gc[gc["share"] > 0].reset_index(drop=True)
    f = np.ones(len(gc))
    f = np.where(gc["category"] == "Kebutuhan Upacara", gc["f_upakara"], f)
    bad = ((gc["category"] == "Minuman") & (gc["date"] >= s["bad_supplier_from"]) &
           (gc["date"] <= s["bad_supplier_to"])).to_numpy()
    f = np.where(bad, f * .86, f)
    gc["campaign_id"] = None
    for c in campaigns.itertuples():
        m = ((gc["category"] == c.target_category) & (gc["date"] >= c.start_date) & (gc["date"] <= c.end_date)).to_numpy().copy()
        if pd.notna(c.target_store_code):
            m &= (gc["store_code"] == c.target_store_code).to_numpy()
        f = np.where(m, f * (1 + c.uplift), f)
        gc.loc[m, "campaign_id"] = c.campaign_id
    gc["net_sales"] = np.round(gc["expected"] * gc["share"] * f * rng.lognormal(0, .12, len(gc))).astype(np.int64)

    # ---- SKU mingguan (dipecah dari total kategori toko x minggu)
    prods = products.copy()
    assort = stores[["store_code", "store_type"]].merge(prods[["sku", "category", "popularity", "supplier_id",
                                                             "sell_price", "cost_price"]], how="cross")
    assort = assort[(assort["category"] != "Makanan Siap Saji") | (assort["store_type"] == "QSR")]
    top = assort.groupby(["store_code", "category"])["popularity"].rank(ascending=False) <= 3
    keep = top | (rng.random(len(assort)) < .9)
    assort = assort[keep].drop(columns="store_type")

    wk = gc.groupby(["store_code", "week_start", "category"], as_index=False)["net_sales"].sum()
    wk = wk.rename(columns={"net_sales": "cat_week_net"})
    sw = wk.merge(assort, on=["store_code", "category"])

    # OOS (hari OOS per minggu) -> memengaruhi bobot SKU
    p_oos = np.full(len(sw), .035)
    badsup = ((sw["supplier_id"] == s["bad_supplier"]) & (sw["week_start"] >= s["bad_supplier_from"]) &
              (sw["week_start"] <= s["bad_supplier_to"])).to_numpy()
    p_oos[badsup] = .32
    p_oos[(sw["store_code"] == s["shrink_store"]).to_numpy()] *= 2.2
    p_oos[sw["store_code"].isin(["BLL01", "BLL02", "BLL03", "BLL04", "BLL05", "KRA01", "KRA02"]).to_numpy()] *= 1.5
    is_oos = rng.random(len(sw)) < p_oos
    sw["days_oos"] = np.where(is_oos, rng.integers(1, 8, len(sw)), 0)
    w = sw["popularity"] * rng.lognormal(0, .25, len(sw)) * (1 - .7 * sw["days_oos"] / 7)
    w = np.maximum(w, 1e-6)
    wsum = w.groupby([sw["store_code"], sw["week_start"], sw["category"]]).transform("sum")
    sw["net_sales"] = _round_to_total(sw["cat_week_net"] * w / wsum, sw["cat_week_net"],
                                      [sw["store_code"], sw["week_start"], sw["category"]])
    sw["qty"] = np.maximum(np.round(sw["net_sales"] / sw["sell_price"]), 0).astype(np.int64)
    sw["cogs"] = np.round(sw["net_sales"] * sw["cost_price"] / sw["sell_price"]).astype(np.int64)

    # COGS kategori harian mengikuti rasio campuran SKU minggu itu
    ratio = sw.groupby(["store_code", "week_start", "category"], as_index=False)[["cogs", "net_sales"]].sum()
    ratio["cogs_ratio"] = (ratio["cogs"] / ratio["net_sales"].replace(0, np.nan)).fillna(.8)
    gc = gc.merge(ratio[["store_code", "week_start", "category", "cogs_ratio"]], on=["store_code", "week_start", "category"])
    gc["cogs"] = np.round(gc["net_sales"] * gc["cogs_ratio"]).astype(np.int64)
    avg_price = sw.groupby(["store_code", "category"])["sell_price"].mean().rename("avg_price").reset_index()
    gc = gc.merge(avg_price, on=["store_code", "category"])
    gc["qty"] = np.maximum(np.round(gc["net_sales"] / gc["avg_price"] * rng.uniform(.9, 1.1, len(gc))), 0).astype(np.int64)

    # ---- stok mingguan
    avg_qty = sw.groupby(["store_code", "sku"])["qty"].transform("mean")
    sw["min_stock"] = np.maximum(np.ceil(avg_qty * .6), 2).astype(np.int64)
    zero = (sw["days_oos"] > 0) & (rng.random(len(sw)) < .6)
    soh = np.round(sw["min_stock"] * rng.uniform(.8, 3.0, len(sw)))
    soh = np.where(sw["days_oos"] > 0, np.round(sw["min_stock"] * rng.uniform(0, .5, len(sw))), soh)
    sw["soh"] = np.where(zero, 0, soh).astype(np.int64)
    sw["oos_flag"] = (sw["days_oos"] > 0).astype(int)

    # ---- toko x hari
    cat_day = gc.groupby(["store_code", "date"], as_index=False).agg(net_sales=("net_sales", "sum"), cogs=("cogs", "sum"),
                                                                      qty=("qty", "sum"))
    promo_day = gc[gc["campaign_id"].notna()].groupby(["store_code", "date"])["net_sales"].sum().rename("camp_sales")
    d = g[["store_code", "date", "month_start", "core", "amb_base", "location_type", "f_high_season"]].merge(
        cat_day, on=["store_code", "date"]).merge(promo_day, on=["store_code", "date"], how="left")
    d["camp_sales"] = d["camp_sales"].fillna(0)
    d["sales_promo"] = np.round(d["net_sales"] * rng.uniform(.10, .18, len(d)) + d["camp_sales"] * .5).astype(np.int64)
    d["sales_promo"] = np.minimum(d["sales_promo"], d["net_sales"])
    d["gross_sales"] = (d["net_sales"] + np.round(d["sales_promo"] * rng.uniform(.10, .16, len(d)) +
                                                  d["net_sales"] * .004)).astype(np.int64)
    amb = d["amb_base"] * np.where((d["location_type"] == "wisata") & (d["f_high_season"] > 0), 1.08, 1) * \
        rng.lognormal(0, .05, len(d))
    d["std"] = np.maximum(np.round(d["net_sales"] / amb), 1).astype(np.int64)
    d["std_promo"] = np.round(d["std"] * np.clip(d["sales_promo"] / d["net_sales"] * rng.uniform(1.1, 1.6, len(d)),
                                                  0, .9)).astype(np.int64)
    d["qty_items"] = d["qty"]
    tgt = d.groupby(["store_code", "month_start"])["core"].transform("mean")
    d["target_spd"] = (np.round(tgt * 1.05 / 1000) * 1000).astype(np.int64)

    sales_daily = d.rename(columns={"date": "sales_date"})[
        ["sales_date", "store_code", "gross_sales", "net_sales", "cogs", "std", "qty_items", "sales_promo",
         "std_promo", "target_spd"]]
    cat_daily = gc.rename(columns={"date": "sales_date"})[["sales_date", "store_code", "category", "net_sales",
                                                           "cogs", "qty"]]
    sku_weekly = sw[["week_start", "store_code", "sku", "qty", "net_sales", "cogs"]]
    stock_weekly = sw[["week_start", "store_code", "sku", "soh", "min_stock", "oos_flag", "days_oos"]]
    return {"fact_sales_daily": sales_daily, "fact_sales_category_daily": cat_daily,
            "fact_sales_sku_weekly": sku_weekly, "fact_stock_weekly": stock_weekly,
            "_assort": assort, "_sw": sw}
