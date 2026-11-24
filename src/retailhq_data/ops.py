"""Supply chain, DC, planogram & display."""
from __future__ import annotations

import numpy as np
import pandas as pd

CHILLER_CATS = {"Minuman", "Susu & Olahan", "Frozen", "Es Batu & Lainnya"}


def make_purchase_orders(rng, sw, products, suppliers, s) -> pd.DataFrame:
    demand = sw.groupby(["week_start", "sku"], as_index=False)["qty"].sum()
    po = demand.merge(products[["sku", "supplier_id"]], on="sku").merge(suppliers[["supplier_id", "lead_time_days"]],
                                                                        on="supplier_id")
    po["po_date"] = po["week_start"] - pd.to_timedelta(po["lead_time_days"] + 2, unit="D")
    po["qty_ordered"] = (np.ceil(po["qty"] * rng.uniform(1.0, 1.15, len(po)) / 6) * 6).astype(np.int64)
    bad = ((po["supplier_id"] == s["bad_supplier"]) & (po["week_start"] >= s["bad_supplier_from"]) &
           (po["week_start"] <= s["bad_supplier_to"])).to_numpy()
    fill = np.clip(np.where(bad, rng.normal(.72, .08, len(po)), rng.normal(.975, .025, len(po))), .3, 1)
    po["qty_received"] = np.floor(po["qty_ordered"] * fill).astype(np.int64)
    po["expected_date"] = po["po_date"] + pd.to_timedelta(po["lead_time_days"], unit="D")
    delay = np.where(bad, rng.integers(2, 7, len(po)), rng.choice([0, 0, 0, 0, 1, 2], len(po)))
    po["received_date"] = po["expected_date"] + pd.to_timedelta(delay, unit="D")
    po["po_id"] = "PO" + po["po_date"].dt.strftime("%Y%m%d") + "-" + po["supplier_id"]
    return po[["po_id", "po_date", "supplier_id", "sku", "qty_ordered", "qty_received", "expected_date",
               "received_date"]].sort_values(["po_date", "po_id", "sku"]).reset_index(drop=True)


def make_dc_shipments(rng, sw, stores, s, end) -> pd.DataFrame:
    wq = sw.groupby(["store_code", "week_start"], as_index=False)["qty"].sum()
    wq = wq.merge(stores[["store_code", "dist_km_dc", "location_type"]], on="store_code")
    rows = []
    for r in wq.itertuples():
        offsets = [1, 4] if r.location_type != "wisata" else [0, 2, 4]
        split = rng.dirichlet(np.ones(len(offsets)) * 8)
        for off, sp in zip(offsets, split):
            rows.append((r.store_code, r.week_start, off, r.qty * sp, r.dist_km_dc))
    d = pd.DataFrame(rows, columns=["store_code", "week_start", "off", "qty", "km"])
    d["planned_date"] = d["week_start"] + pd.to_timedelta(d["off"], unit="D") - pd.Timedelta(days=1)
    d = d[d["planned_date"] <= pd.Timestamp(end)]
    d["ship_date"] = d["planned_date"]
    d["qty_requested"] = np.round(d["qty"] * rng.uniform(1.0, 1.1, len(d))).astype(np.int64)
    bad = ((d["week_start"] >= s["bad_supplier_from"]) & (d["week_start"] <= s["bad_supplier_to"])).to_numpy()
    fill = np.clip(rng.normal(.965, .02, len(d)) - np.where(bad, .05, 0), .6, 1)
    d["qty_shipped"] = np.floor(d["qty_requested"] * fill).astype(np.int64)
    p_late = .04 + d["km"] / 900
    late = rng.random(len(d)) < p_late
    d["delivered_date"] = d["planned_date"] + pd.to_timedelta(np.where(late, rng.integers(1, 3, len(d)), 0), unit="D")
    d["delivery_cost"] = (np.round((150_000 + 4_500 * d["km"]) * rng.uniform(.9, 1.15, len(d)), -3)).astype(np.int64)
    d = d.sort_values(["ship_date", "store_code"]).reset_index(drop=True)
    d["shipment_id"] = "SHP" + (d.index + 1).astype(str).str.zfill(6)
    return d[["shipment_id", "ship_date", "store_code", "qty_requested", "qty_shipped", "planned_date",
              "delivered_date", "delivery_cost"]]


def make_fixtures(rng, stores) -> pd.DataFrame:
    rows = []
    spec = {"gondola": (5, "tengah"), "chiller": (5, "belakang"), "end gondola": (4, "depan"), "kasir": (3, "depan"),
            "rak promo": (3, "depan")}
    for st in stores.itertuples():
        counts = {"gondola": int(st.size_m2 // 14), "chiller": int(rng.integers(3, 7)),
                  "end gondola": int(rng.integers(4, 9)), "kasir": 2 if st.size_m2 > 170 else 1,
                  "rak promo": int(rng.integers(2, 4))}
        if st.store_type == "QSR":
            counts["takeout"] = 2
        n = 0
        for ftype, c in counts.items():
            for _ in range(c):
                n += 1
                shelves, zone = spec.get(ftype, (3, "takeout"))
                if ftype == "takeout":
                    ftype, zone = "rak promo", "takeout"
                rows.append({"fixture_id": f"{st.store_code}-F{n:02d}", "store_code": st.store_code,
                             "fixture_type": ftype, "zone": zone, "shelf_count": shelves,
                             "length_cm": int(rng.choice([90, 120, 150, 180]))})
    return pd.DataFrame(rows)


def make_planogram(rng, assort, fixtures, start) -> pd.DataFrame:
    a = assort[["store_code", "sku", "category", "popularity"]].copy()
    a["ftype"] = np.where(a["category"].isin(CHILLER_CATS), "chiller",
                          np.where(a["category"] == "Rokok", "kasir", "gondola"))
    fx = fixtures[fixtures["fixture_type"].isin(["gondola", "chiller", "kasir"])]
    out = []
    for (store, ftype), grp in a.groupby(["store_code", "ftype"]):
        ids = fx.loc[(fx["store_code"] == store) & (fx["fixture_type"] == ftype), "fixture_id"].to_numpy()
        grp = grp.sort_values(["category", "popularity"], ascending=[True, False])
        grp = grp.assign(fixture_id=ids[np.arange(len(grp)) * len(ids) // len(grp)])
        out.append(grp)
    p = pd.concat(out, ignore_index=True)
    levels = np.array(["atas", "eye level", "tangan", "bawah"])
    rank = p.groupby(["store_code", "fixture_id"])["popularity"].rank(ascending=False, pct=True)
    p["shelf_level"] = np.where(rank <= .3, "eye level", np.where(rank <= .6, "tangan",
                                                                 levels[rng.choice([0, 3], len(p))]))
    p["facings"] = np.clip(np.round(1 + 3 * (1 - rank) + rng.normal(0, .5, len(p))), 1, 5).astype(int)
    p["position"] = p.groupby(["store_code", "fixture_id", "shelf_level"]).cumcount() + 1
    p["effective_from"] = pd.Timestamp(start)
    p["effective_to"] = pd.Timestamp("2025-06-30")
    v2 = p.copy()
    move = rng.random(len(v2)) < .2
    v2.loc[move, "shelf_level"] = rng.choice(levels, int(move.sum()))
    v2["facings"] = np.clip(v2["facings"] + rng.choice([-1, 0, 0, 1], len(v2)), 1, 5)
    v2["position"] = v2.groupby(["store_code", "fixture_id", "shelf_level"]).cumcount() + 1
    v2["effective_from"] = pd.Timestamp("2025-07-01")
    v2["effective_to"] = pd.NaT
    p = pd.concat([p, v2], ignore_index=True)
    return p[["store_code", "fixture_id", "shelf_level", "sku", "facings", "position", "effective_from", "effective_to"]]


def make_display_audit(rng, planogram, stores, s, start, end) -> pd.DataFrame:
    bad_stores = set(stores.loc[stores["am_name"] == s["planogram_am"], "store_code"])
    rows = []
    for m in pd.date_range(start, end, freq="MS"):
        ver = planogram[(planogram["effective_from"] <= m) & (planogram["effective_to"].isna() |
                                                              (planogram["effective_to"] >= m))]
        open_stores = stores.loc[stores["open_date"] <= m, "store_code"]
        sample = ver[ver["store_code"].isin(open_stores)].groupby("store_code").sample(n=30, random_state=int(rng.integers(1e9)))
        sample = sample.assign(audit_date=m + pd.to_timedelta(rng.integers(3, 25, len(sample)), unit="D"))
        rows.append(sample)
    a = pd.concat(rows, ignore_index=True)
    bad = a["store_code"].isin(bad_stores).to_numpy()
    miss = rng.random(len(a)) < np.where(bad, .30, .07)
    a["planned_facings"] = a["facings"]
    a["actual_facings"] = np.where(miss, np.maximum(a["facings"] - rng.integers(1, 3, len(a)), 0), a["facings"])
    a["price_tag_ok"] = rng.random(len(a)) > np.where(bad, .22, .05)
    a["shelf_talker_ok"] = rng.random(len(a)) > np.where(bad, .28, .09)
    return a[["audit_date", "store_code", "fixture_id", "sku", "planned_facings", "actual_facings", "price_tag_ok",
              "shelf_talker_ok"]].sort_values(["audit_date", "store_code"]).reset_index(drop=True)


def make_secondary_display(rng, campaigns, assort, stores) -> pd.DataFrame:
    rows = []
    for c in campaigns.itertuples():
        targets = [c.target_store_code] if pd.notna(c.target_store_code) else stores.loc[stores["open_date"] <= c.start_date,
                                                                                "store_code"].tolist()
        for st in targets:
            pool = assort[(assort["store_code"] == st) & (assort["category"] == c.target_category)]
            if pool.empty:
                continue
            for sku in pool.nlargest(int(rng.integers(2, 5)), "popularity")["sku"]:
                rows.append({"store_code": st, "sku": sku,
                             "display_type": rng.choice(["end gondola", "rak promo", "dekat kasir"]),
                             "start_date": c.start_date, "end_date": c.end_date})
    return pd.DataFrame(rows)
