"""Cek integritas data sebelum ditulis. Mengembalikan daftar masalah (kosong = lolos)."""
from __future__ import annotations

import pandas as pd

PK = {
    "dim_store": ["store_code"], "dim_product": ["sku"], "dim_supplier": ["supplier_id"],
    "dim_employee": ["employee_id"], "dim_fixture": ["fixture_id"], "dim_contract": ["contract_id"],
    "dim_it_asset": ["asset_id"], "dim_member": ["member_id"],
    "fact_sales_daily": ["sales_date", "store_code"],
    "fact_sales_category_daily": ["sales_date", "store_code", "category"],
    "fact_sales_sku_weekly": ["week_start", "store_code", "sku"],
    "fact_stock_weekly": ["week_start", "store_code", "sku"],
    "fact_planogram": ["store_code", "sku", "effective_from"],
    "fact_purchase_order": ["po_id", "sku"], "fact_dc_shipment": ["shipment_id"],
    "fact_shift": ["work_date", "employee_id"], "fact_opex_monthly": ["month", "store_code"],
    "fact_budget_monthly": ["month", "store_code"], "fact_capex_project": ["project_id"],
    "fact_it_ticket": ["ticket_id"], "fact_pos_downtime": ["downtime_date", "store_code"],
    "fact_member_monthly": ["month", "member_id", "store_code"], "fact_campaign": ["campaign_id"],
    "fact_stock_opname": ["opname_date", "store_code", "sku"],
    "fact_pos_void": ["void_date", "cashier_id"], "fact_cash_variance": ["variance_date", "cashier_id"],
    "fact_energy_monthly": ["month", "store_code"], "fact_waste_monthly": ["month", "store_code"],
    "fact_plastic_monthly": ["month", "store_code"],
}
FK = [("store_code", "dim_store", "store_code"), ("home_store_code", "dim_store", "store_code"),
      ("target_store_code", "dim_store", "store_code"), ("sku", "dim_product", "sku"),
      ("supplier_id", "dim_supplier", "supplier_id"), ("employee_id", "dim_employee", "employee_id"),
      ("fixture_id", "dim_fixture", "fixture_id"), ("member_id", "dim_member", "member_id")]


def validate(t: dict[str, pd.DataFrame], nyepi: list[str]) -> list[str]:
    p: list[str] = []
    for name, keys in PK.items():
        d = t[name].duplicated(keys).sum()
        if d:
            p.append(f"{name}: {d} duplikat pada kunci {keys}")
    for name, df in t.items():
        for col, ref, rcol in FK:
            if col in df.columns and name != ref:
                bad = ~df[col].dropna().isin(t[ref][rcol])
                if bad.any():
                    p.append(f"{name}.{col}: {bad.sum()} nilai tidak ada di {ref}")
        num = df.select_dtypes("number")
        neg = (num < 0).sum()
        if neg.any():
            p.append(f"{name}: nilai negatif di {neg[neg > 0].to_dict()}")

    sd, cd, sw = t["fact_sales_daily"], t["fact_sales_category_daily"], t["fact_sales_sku_weekly"]
    agg = cd.groupby(["sales_date", "store_code"])[["net_sales", "cogs"]].sum()
    m = sd.set_index(["sales_date", "store_code"])[["net_sales", "cogs"]].join(agg, rsuffix="_cat")
    if (m["net_sales"] != m["net_sales_cat"]).any() or (m["cogs"] != m["cogs_cat"]).any():
        p.append("fact_sales_daily tidak sama dengan jumlah fact_sales_category_daily")
    cw = cd.assign(week_start=cd["sales_date"] - pd.to_timedelta(cd["sales_date"].dt.dayofweek, unit="D")) \
        .groupby(["week_start", "store_code"])["net_sales"].sum()
    sk = sw.groupby(["week_start", "store_code"])["net_sales"].sum()
    if not cw.sort_index().equals(sk.sort_index()):
        p.append("fact_sales_sku_weekly tidak sama dengan kategori harian per minggu")
    if sd["sales_date"].isin(pd.to_datetime(nyepi)).any():
        p.append("ada penjualan di hari Nyepi")
    od = t["dim_store"].set_index("store_code")["open_date"]
    if (sd["sales_date"] < sd["store_code"].map(od)).any():
        p.append("ada penjualan sebelum toko buka")
    if (sd["net_sales"] > sd["gross_sales"]).any():
        p.append("net_sales > gross_sales")
    if (sd["std_promo"] > sd["std"]).any() or (sd["sales_promo"] > sd["net_sales"]).any():
        p.append("promo melebihi total")
    st = t["fact_stock_weekly"]
    if ((st["soh"] == 0) & (st["days_oos"] == 0)).any():
        p.append("SOH 0 tapi days_oos 0")
    po = t["fact_purchase_order"]
    if (po["qty_received"] > po["qty_ordered"]).any():
        p.append("qty_received > qty_ordered")
    return p
