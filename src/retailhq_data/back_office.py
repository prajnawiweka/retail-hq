"""HR, Finance, Legal, Store Dev, IT, Marketing/CRM, Loss Prevention, ESG."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .sales import BASE_SHARE, LOC_ADJ

# Upah dasar asumsi dummy (mendekati skala UMK, bukan angka resmi)
WAGE = {"Badung": 3_600_000, "Denpasar": 3_300_000, "Gianyar": 3_200_000, "Tabanan": 3_100_000,
        "Buleleng": 2_950_000, "Klungkung": 2_850_000, "Karangasem": 2_850_000, "Bangli": 2_800_000}
POS_MULT = {"Kepala Toko": 2.0, "Asisten Kepala Toko": 1.4, "Kasir": 1.0, "Pramuniaga": 1.0, "Crew QSR": 1.05}


# ---------------- HR
def make_employees(rng, stores, s, start, end) -> pd.DataFrame:
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    rows = []
    eid = 0
    for st in stores.itertuples():
        slots = ["Kepala Toko", "Asisten Kepala Toko"] + ["Kasir"] * (4 if st.size_m2 > 170 else 3) + \
                ["Pramuniaga"] * (4 if st.location_type == "wisata" else 3) + (["Crew QSR"] * 3 if st.store_type == "QSR" else [])
        p_exit = .07 if st.store_code == s["hr_store"] else .022
        for pos in slots:
            hire = min(st.open_date, start) - pd.Timedelta(days=int(rng.integers(0, 1500))) if st.open_date < start \
                else st.open_date - pd.Timedelta(days=int(rng.integers(5, 25)))
            hire = max(hire, st.open_date - pd.Timedelta(days=30))
            while hire <= end:
                months_stay = rng.geometric(p_exit * (.5 if pos == "Kepala Toko" else 1))
                exit_ = hire + pd.Timedelta(days=int(months_stay * 30.4))
                eid += 1
                sal = WAGE[st.regency] * POS_MULT[pos] * rng.uniform(1.0, 1.12)
                rows.append({"employee_id": f"EMP{eid:05d}", "store_code": st.store_code, "position": pos,
                             "hire_date": hire, "exit_date": exit_ if exit_ <= end else pd.NaT,
                             "monthly_salary": int(round(sal, -3))})
                if exit_ > end:
                    break
                hire = exit_ + pd.Timedelta(days=int(rng.integers(7, 21)))
    e = pd.DataFrame(rows)
    return e[(e["exit_date"].isna()) | (e["exit_date"] >= start - pd.Timedelta(days=365))].reset_index(drop=True)


def make_shifts(rng, employees, sales_daily, s) -> pd.DataFrame:
    open_days = sales_daily[["store_code", "sales_date", "net_sales"]].rename(columns={"sales_date": "work_date"})
    m = employees.merge(open_days, on="store_code")
    m = m[(m["work_date"] >= m["hire_date"]) & (m["exit_date"].isna() | (m["work_date"] < m["exit_date"]))]
    day_off = m["employee_id"].str[-1].astype(int) % 7
    m = m[m["work_date"].dt.dayofweek != day_off].copy()
    busy = m["net_sales"] / m.groupby("store_code")["net_sales"].transform("median")
    p_ot = np.clip(.10 + .35 * (busy - 1), .02, .6)
    p_ot = np.where(m["store_code"] == s["hr_store"], np.maximum(p_ot, .5), p_ot)
    ot = rng.random(len(m)) < p_ot
    m["hours_worked"] = np.round(rng.normal(8, .3, len(m)) * 2) / 2
    m["overtime_hours"] = np.where(ot, rng.choice([1, 1, 2, 2, 3, 4], len(m)), 0)
    return m[["work_date", "store_code", "employee_id", "hours_worked", "overtime_hours"]].sort_values(
        ["work_date", "store_code"]).reset_index(drop=True)


# ---------------- Legal
def make_contracts(rng, stores, s) -> pd.DataFrame:
    rows = []
    n = 0
    rate = {"wisata": 1_700_000, "jalan utama": 1_200_000, "perumahan": 920_000, "dekat kampus": 1_000_000}
    expiring = stores.loc[stores["open_date"] < "2022-01-01", "store_code"].iloc[[3, 11, 27]].tolist()
    for st in stores.itertuples():
        n += 1
        start = st.open_date
        end = start + pd.DateOffset(years=5)
        while end < pd.Timestamp("2026-11-01"):
            start, end = end, end + pd.DateOffset(years=5)
        if st.store_code in expiring:
            end = pd.Timestamp("2026-11-15") + pd.Timedelta(days=int(rng.integers(0, 120)))
        annual = st.size_m2 * rate[st.location_type] * rng.uniform(.85, 1.2)
        if st.store_code == s["loss_store"]:
            annual *= 3.4
        rows.append({"contract_id": f"CTR{n:04d}", "store_code": st.store_code, "vendor_name": f"Pemilik Ruko {st.district}",
                     "contract_type": "sewa", "start_date": start, "end_date": end, "annual_value": int(round(annual, -5)),
                     "escalation_pct": float(10 if st.store_code == expiring[0] else rng.choice([3, 5, 5, 7])),
                     "status": "aktif"})
        n += 1
        iz_end = st.open_date + pd.DateOffset(years=5)
        while iz_end < pd.Timestamp("2026-06-01"):
            iz_end = iz_end + pd.DateOffset(years=5)
        rows.append({"contract_id": f"CTR{n:04d}", "store_code": st.store_code, "vendor_name": "Pemda " + st.regency,
                     "contract_type": "izin", "start_date": iz_end - pd.DateOffset(years=5), "end_date": iz_end,
                     "annual_value": 0, "escalation_pct": 0.0, "status": "aktif"})
        for vendor, lo, hi in [("CV Bersih Sejahtera (kebersihan)", 18e6, 30e6), ("PT Satpam Bali Aman (keamanan)", 30e6, 48e6),
                               ("UD Sampah Mandiri (angkut sampah)", 6e6, 12e6)]:
            n += 1
            vs = pd.Timestamp("2025-01-01") + pd.Timedelta(days=int(rng.integers(0, 300)))
            rows.append({"contract_id": f"CTR{n:04d}", "store_code": st.store_code, "vendor_name": vendor,
                         "contract_type": "vendor", "start_date": vs, "end_date": vs + pd.DateOffset(years=2),
                         "annual_value": int(round(rng.uniform(lo, hi), -5)), "escalation_pct": 0.0, "status": "aktif"})
    return pd.DataFrame(rows)


# ---------------- Store Dev
def make_capex(rng, stores, s) -> pd.DataFrame:
    rows = []
    n = 0
    for st in stores[stores["open_date"] >= "2024-11-01"].itertuples():
        n += 1
        rows.append({"project_id": f"PRJ{n:03d}", "store_code": st.store_code, "project_type": "baru",
                     "capex_amount": int(round(rng.uniform(1.3e9, 1.9e9), -6)),
                     "start_date": st.open_date - pd.Timedelta(days=int(rng.integers(90, 150))),
                     "open_date": st.open_date, "status": "selesai"})
    old = stores[stores["open_date"] < "2019-01-01"]
    statuses = ["selesai"] * 5 + ["berjalan", "rencana", "rencana"]
    for j, (st, status) in enumerate(zip(old.sample(8, random_state=int(rng.integers(1e9))).itertuples(), statuses)):
        n += 1
        sd = {"selesai": pd.Timestamp("2025-01-10") + pd.Timedelta(days=int(rng.integers(0, 400))),
              "berjalan": pd.Timestamp("2026-09-15"), "rencana": pd.Timestamp("2027-02-01")}[status]
        ptype = "relokasi" if j == len(statuses) - 1 else "renovasi"
        rows.append({"project_id": f"PRJ{n:03d}", "store_code": st.store_code, "project_type": ptype,
                     "capex_amount": int(round(rng.uniform(1.5e8, 4.5e8) if ptype == "renovasi" else 1.2e9, -6)),
                     "start_date": sd, "open_date": sd + pd.Timedelta(days=int(rng.integers(14, 45))), "status": status})
    return pd.DataFrame(rows)


# ---------------- IT
def make_it(rng, stores, s, start, end):
    assets = []
    n = 0
    for st in stores.itertuples():
        nk = 2 if st.size_m2 > 170 else 1
        spec = [("POS", nk + 1), ("printer", nk + 1), ("CCTV", int(rng.integers(4, 9))), ("jaringan", 2)]
        for atype, c in spec:
            for _ in range(c):
                n += 1
                pdate = pd.Timestamp("2018-03-01") if (st.store_code == s["it_store"] and atype == "POS") else \
                    max(st.open_date, pd.Timestamp("2018-01-01")) + pd.Timedelta(days=int(rng.integers(0, 1500)))
                assets.append({"asset_id": f"AST{n:05d}", "store_code": st.store_code, "asset_type": atype,
                               "purchase_date": min(pdate, pd.Timestamp(end)), "status": "aktif"})
    a = pd.DataFrame(assets)
    a.loc[rng.random(len(a)) < .03, "status"] = "rusak"

    months = pd.date_range(start, end, freq="MS")
    tix = []
    for m in months:
        age = (m - a["purchase_date"]).dt.days.clip(lower=0) / 365
        lam = .015 + .012 * age
        lam = np.where((a["store_code"] == s["it_store"]) & (a["asset_type"] == "POS"), lam * 5, lam)
        k = rng.poisson(lam)
        for idx in np.nonzero(k)[0]:
            for _ in range(k[idx]):
                tix.append((a.at[idx, "store_code"], a.at[idx, "asset_type"], m))
    t = pd.DataFrame(tix, columns=["store_code", "asset_type", "month"])
    cat_map = {"POS": "POS error", "printer": "printer struk", "CCTV": "CCTV", "jaringan": "jaringan/internet"}
    t["category"] = t["asset_type"].map(cat_map)
    t["priority"] = np.where(t["asset_type"].isin(["POS", "jaringan"]), rng.choice(["tinggi", "sedang"], len(t), p=[.6, .4]),
                             rng.choice(["sedang", "rendah"], len(t), p=[.4, .6]))
    t["opened_at"] = t["month"] + pd.to_timedelta(rng.integers(0, 28 * 24 * 60, len(t)), unit="m")
    hrs = rng.lognormal(np.where(t["priority"] == "tinggi", 1.2, 2.3), .7)
    t["resolved_at"] = t["opened_at"] + pd.to_timedelta(np.round(hrs * 60), unit="m")
    t.loc[t["resolved_at"] > pd.Timestamp(end) + pd.Timedelta(days=1), "resolved_at"] = pd.NaT
    t = t.sort_values("opened_at").reset_index(drop=True)
    t["ticket_id"] = "TKT" + (t.index + 1).astype(str).str.zfill(5)
    t["opened_at"] = t["opened_at"].dt.floor("min")
    t["resolved_at"] = t["resolved_at"].dt.floor("min")
    return a, t[["ticket_id", "store_code", "category", "priority", "opened_at", "resolved_at"]]


def make_pos_downtime(rng, sales_daily, s) -> pd.DataFrame:
    d = sales_daily[["sales_date", "store_code"]].rename(columns={"sales_date": "downtime_date"})
    p = np.where(d["store_code"] == s["it_store"], .18, .03)
    d = d[rng.random(len(d)) < p].copy()
    d["downtime_minutes"] = np.clip(np.round(rng.lognormal(3.2, .8, len(d))), 3, 480).astype(int)
    return d.reset_index(drop=True)


# ---------------- Marketing / CRM
def make_members(rng, cfg, stores, sales_daily, start, end):
    n = cfg["n_members"]
    vol = sales_daily.groupby("store_code")["net_sales"].sum()
    w = (vol / vol.sum()).reindex(stores["store_code"]).fillna(0).to_numpy()
    home = rng.choice(stores["store_code"], n, p=w)
    loc = stores.set_index("store_code").loc[home, "location_type"].to_numpy()
    mtype = np.where(loc == "wisata", rng.choice(["lokal", "turis", "ekspat"], n, p=[.4, .4, .2]),
                     rng.choice(["lokal", "turis", "ekspat"], n, p=[.9, .05, .05]))
    join = pd.Timestamp("2019-01-01") + pd.to_timedelta(rng.integers(0, (pd.Timestamp(end) - pd.Timestamp("2019-01-01")).days, n), unit="D")
    m = pd.DataFrame({"member_id": [f"MBR{i + 1:06d}" for i in range(n)], "home_store_code": home,
                      "age_group": rng.choice(["<20", "20-29", "30-39", "40-49", "50+"], n, p=[.08, .32, .28, .18, .14]),
                      "gender": rng.choice(["P", "L"], n, p=[.56, .44]), "member_type": mtype, "join_date": join})
    opened = stores.set_index("store_code").loc[home, "open_date"].to_numpy()
    m["join_date"] = np.maximum(m["join_date"].to_numpy(), opened)

    months = pd.date_range(start, end, freq="MS")
    life = np.where(mtype == "turis", rng.integers(1, 3, n), rng.geometric(.04, n))  # bulan aktif
    first = np.maximum(((m["join_date"].dt.year - months[0].year) * 12 + m["join_date"].dt.month - months[0].month), 0)
    rows = []
    for i, mo in enumerate(months):
        active = (first <= i) & (i < first + life) & (m["join_date"] <= mo + pd.offsets.MonthEnd(0))
        idx = np.nonzero(active.to_numpy())[0]
        lam = np.select([mtype[idx] == "ekspat", mtype[idx] == "turis"], [5.0, 3.0], 3.5)
        visits = rng.poisson(lam)
        keep = visits > 0
        idx, visits = idx[keep], visits[keep]
        store = np.where(rng.random(len(idx)) < .85, home[idx], rng.choice(stores["store_code"], len(idx)))
        amb = np.select([mtype[idx] == "ekspat", mtype[idx] == "turis"], [95000, 80000], 55000) * rng.lognormal(0, .3, len(idx))
        rows.append(pd.DataFrame({"month": mo, "member_id": m["member_id"].to_numpy()[idx], "store_code": store,
                                  "visits": visits, "net_sales": np.round(visits * amb, -2).astype(np.int64)}))
    mm = pd.concat(rows, ignore_index=True)
    cats = list(BASE_SHARE)
    shares = np.array([BASE_SHARE[c] for c in cats], float)
    shares[cats.index("Makanan Siap Saji")] = 3
    mm["top_category"] = rng.choice(cats, len(mm), p=shares / shares.sum())
    # Pastikan member tidak belanja di toko yang belum buka
    od = stores.set_index("store_code")["open_date"]
    mm = mm[mm["month"] >= od.loc[mm["store_code"]].to_numpy().astype("datetime64[M]")]
    return m, mm.reset_index(drop=True)


# ---------------- Loss Prevention
def make_loss_prevention(rng, sw, products, sales_daily, stores, s):
    cost = products.set_index("sku")["cost_price"]
    # stock opname tiap kuartal (Feb, Mei, Agu, Nov), minggu kedua
    sw = sw.copy()
    sw["m"] = sw["week_start"].dt.month
    opn = sw[sw["m"].isin([2, 5, 8, 11]) & sw["week_start"].dt.day.between(8, 14)].copy()
    shrink_lam = np.where(opn["store_code"] == s["shrink_store"], .9, .25)
    loss = rng.poisson(shrink_lam) * (rng.random(len(opn)) < .5)
    gain = (rng.random(len(opn)) < .03).astype(int)
    opn["system_qty"] = opn["soh"] + rng.integers(0, 3, len(opn))
    opn["physical_qty"] = np.maximum(opn["system_qty"] - loss + gain, 0)
    opn["opname_date"] = opn["week_start"] + pd.Timedelta(days=2)
    stock_opname = opn[["opname_date", "store_code", "sku", "system_qty", "physical_qty"]].reset_index(drop=True)

    # write-off
    perish = sw["sku"].map(products.set_index("sku")["category"]).isin(["Roti & Kue", "Susu & Olahan", "Makanan Siap Saji", "Frozen"])
    p = np.where(perish, .05, .006)
    p = np.where(sw["store_code"] == s["shrink_store"], p * 1.5, p)
    w = sw[rng.random(len(sw)) < p].copy()
    w_perish = w["sku"].map(products.set_index("sku")["category"]).isin(["Roti & Kue", "Susu & Olahan", "Makanan Siap Saji", "Frozen"])
    w["reason"] = np.where(w_perish, rng.choice(["expired", "rusak"], len(w), p=[.7, .3]),
                           rng.choice(["rusak", "hilang"], len(w), p=[.6, .4]))
    w.loc[(w["store_code"] == s["shrink_store"]) & (rng.random(len(w)) < .5), "reason"] = "hilang"
    w["qty"] = rng.integers(1, 6, len(w))
    w["value"] = (w["qty"] * w["sku"].map(cost)).astype(np.int64)
    w["writeoff_date"] = w["week_start"] + pd.to_timedelta(rng.integers(0, 7, len(w)), unit="D")
    writeoff = w[["writeoff_date", "store_code", "sku", "qty", "reason", "value"]].reset_index(drop=True)

    # void, refund, selisih kas per kasir per hari
    nk = stores.set_index("store_code")["size_m2"].gt(170).map({True: 3, False: 2})
    d = sales_daily[["sales_date", "store_code", "net_sales"]]
    reps = d.loc[d.index.repeat(d["store_code"].map(nk))].copy()
    reps["slot"] = reps.groupby(["sales_date", "store_code"]).cumcount() + 1
    reps["cashier_id"] = reps["store_code"] + "-KSR" + reps["slot"].astype(str)
    bad = (reps["cashier_id"] == f"{s['shrink_store']}-{s['shrink_cashier']}").to_numpy()
    reps["void_count"] = rng.poisson(np.where(bad, 5.0, 1.2))
    reps["void_value"] = np.round(reps["void_count"] * rng.lognormal(np.log(25000), .5, len(reps)), -2).astype(np.int64)
    reps["refund_count"] = rng.poisson(np.where(bad, 1.6, .25))
    reps["refund_value"] = np.round(reps["refund_count"] * rng.lognormal(np.log(42000), .5, len(reps)), -2).astype(np.int64)
    pos_void = reps[["sales_date", "store_code", "cashier_id", "void_count", "void_value", "refund_count", "refund_value"]] \
        .rename(columns={"sales_date": "void_date"}).reset_index(drop=True)
    share = 1 / reps["store_code"].map(nk)
    reps["expected_cash"] = np.round(reps["net_sales"] * .55 * share * rng.uniform(.8, 1.2, len(reps)), -2).astype(np.int64)
    noise = np.round(rng.normal(0, 4000, len(reps)) / 500) * 500
    noise = np.where(rng.random(len(reps)) < .7, 0, noise)
    short = np.where(bad & (rng.random(len(reps)) < .4), -np.round(rng.uniform(10000, 60000, len(reps)), -3), 0)
    reps["actual_cash"] = (reps["expected_cash"] + noise + short).astype(np.int64)
    cash = reps[["sales_date", "store_code", "cashier_id", "expected_cash", "actual_cash"]] \
        .rename(columns={"sales_date": "variance_date"}).reset_index(drop=True)
    return stock_opname, writeoff, pos_void, cash


# ---------------- ESG
def make_esg(rng, stores, fixtures, sales_daily, s):
    days = sales_daily.assign(month=sales_daily["sales_date"].values.astype("datetime64[M]")) \
        .groupby(["store_code", "month"], as_index=False).agg(open_days=("sales_date", "count"), net_sales=("net_sales", "sum"),
                                                               std=("std", "sum"))
    e = days.merge(stores[["store_code", "size_m2", "store_type"]], on="store_code")
    ch = fixtures[fixtures["fixture_type"] == "chiller"].groupby("store_code").size().rename("chillers")
    e = e.merge(ch, on="store_code", how="left")
    mon = pd.to_datetime(e["month"]).dt.month
    hot = np.where(mon.isin([10, 11, 12, 1, 2, 3]), 1.15, .95)
    chf = np.where(e["store_code"] == s["energy_store"], 1.35, 1.0)
    e["kwh_chiller"] = np.round(e["chillers"] * 15 * e["open_days"] * hot * chf * rng.uniform(.95, 1.05, len(e))).astype(int)
    e["kwh_ac"] = np.round(e["size_m2"] * .45 * e["open_days"] * hot * rng.uniform(.9, 1.1, len(e))).astype(int)
    other = np.round(e["size_m2"] * .3 * e["open_days"] * np.where(e["store_type"] == "QSR", 1.5, 1)).astype(int)
    e["kwh_total"] = e["kwh_chiller"] + e["kwh_ac"] + other
    e["energy_cost"] = np.round(e["kwh_total"] * 1700, -3).astype(np.int64)  # asumsi tarif Rp1.700/kWh
    energy = e[["month", "store_code", "kwh_total", "kwh_chiller", "kwh_ac", "energy_cost"]]

    qsr = np.where(e["store_type"] == "QSR", 2.2, 1.0)
    waste = pd.DataFrame({"month": e["month"], "store_code": e["store_code"],
                          "general_waste_kg": np.round(e["open_days"] * rng.uniform(4, 7, len(e)), 1),
                          "food_waste_kg": np.round(e["open_days"] * rng.uniform(.8, 1.6, len(e)) * qsr, 1)})
    waste["recycled_kg"] = np.round(waste["general_waste_kg"] * rng.uniform(.15, .35, len(e)), 1)
    # Bali membatasi kantong plastik sekali pakai (Pergub 97/2018):
    # used = kantong plastik kecil untuk produk curah/fresh; sold = tas belanja guna ulang yang terjual
    plastic = pd.DataFrame({"month": e["month"], "store_code": e["store_code"],
                            "plastic_bags_used": np.round(e["open_days"] * rng.uniform(3, 12, len(e)) * qsr).astype(int),
                            "plastic_bags_sold": np.round(e["std"] * rng.uniform(.004, .012, len(e))).astype(int)})
    return energy, waste, plastic


# ---------------- Finance
def make_finance(rng, stores, sales_daily, employees, contracts, energy, campaigns, it_tickets, start, end):
    sd = sales_daily.assign(month=sales_daily["sales_date"].values.astype("datetime64[M]"))
    base = sd.groupby(["store_code", "month"], as_index=False).agg(budget_sales=("target_spd", "sum"),
                                                                    open_days=("sales_date", "count"))
    rent = contracts[contracts["contract_type"] == "sewa"].set_index("store_code")["annual_value"] / 12
    vendors = contracts[contracts["contract_type"] == "vendor"].groupby("store_code")["annual_value"].sum() / 12
    o = base.copy()
    o["rent"] = np.round(o["store_code"].map(rent)).astype(np.int64)

    # gaji: prorata hari aktif karyawan
    rows = []
    for mo in pd.date_range(start, end, freq="MS"):
        me = mo + pd.offsets.MonthEnd(0)
        act = employees[(employees["hire_date"] <= me) & (employees["exit_date"].isna() | (employees["exit_date"] >= mo))]
        a0 = act["hire_date"].where(act["hire_date"] > mo, mo)
        a1 = act["exit_date"].fillna(me).where(act["exit_date"].fillna(me) < me, me)
        frac = ((a1 - a0).dt.days + 1) / me.day
        rows.append(pd.DataFrame({"store_code": act["store_code"], "month": mo, "salary": act["monthly_salary"] * frac}))
    sal = pd.concat(rows).groupby(["store_code", "month"], as_index=False)["salary"].sum()
    o = o.merge(sal, on=["store_code", "month"], how="left")
    o["salary"] = np.round(o["salary"].fillna(0) * 1.08).astype(np.int64)  # + BPJS & tunjangan
    o = o.merge(energy[["store_code", "month", "energy_cost"]], on=["store_code", "month"])
    o["utilities"] = (o["energy_cost"] + np.round(rng.uniform(4e5, 9e5, len(o)), -3)).astype(np.int64)
    o["maintenance"] = np.round(rng.uniform(1.2e6, 3.5e6, len(o)) + (rng.random(len(o)) < .05) * rng.uniform(5e6, 2e7, len(o)), -3).astype(np.int64)

    n_open = o.groupby("month")["store_code"].transform("count")
    promo = np.zeros(len(o))
    for c in campaigns.itertuples():
        mo = c.start_date.to_period("M").to_timestamp()
        if pd.notna(c.target_store_code):
            promo += np.where((o["month"] == mo) & (o["store_code"] == c.target_store_code), c.cost, 0)
        else:
            promo += np.where(o["month"] == mo, c.cost / n_open, 0)
    o["promo_cost"] = np.round(promo + rng.uniform(3e5, 8e5, len(o)), -3).astype(np.int64)
    tk = it_tickets.assign(month=it_tickets["opened_at"].values.astype("datetime64[M]")).groupby(["store_code", "month"]).size()
    o["it_cost"] = (1_250_000 + o.set_index(["store_code", "month"]).index.map(tk).fillna(0).to_numpy() * 175_000).astype(np.int64)
    o["other_cost"] = np.round(o["store_code"].map(vendors).fillna(0) + rng.uniform(5e5, 1.5e6, len(o)), -3).astype(np.int64)
    opex = o[["month", "store_code", "rent", "salary", "utilities", "maintenance", "promo_cost", "it_cost", "other_cost"]]
    tot = opex[["rent", "salary", "utilities", "maintenance", "promo_cost", "it_cost", "other_cost"]].sum(axis=1)
    budget = pd.DataFrame({"month": o["month"], "store_code": o["store_code"], "budget_sales": o["budget_sales"],
                           "budget_opex": np.round(tot.groupby(o["store_code"]).transform("median") * .97, -3).astype(np.int64)})
    return opex, budget
