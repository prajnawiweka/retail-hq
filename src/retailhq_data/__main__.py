"""Generate data dummy Retail HQ.

Pakai:  uv run python -m retailhq_data            (output ke data/raw)
        uv run python -m retailhq_data --out data/raw --seed 42
"""
from __future__ import annotations

import argparse
import sys
import time
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

from . import back_office as bo
from . import ops
from .calendar_bali import NYEPI, build_calendar
from .masters import make_products, make_stores, make_suppliers
from .sales import make_campaigns, simulate_sales
from .stories import answer_key, pick_stories
from .validate import validate

ROOT = Path(__file__).resolve().parents[2]
GZIP_TABLES = {"fact_sales_sku_weekly", "fact_stock_weekly"}  # > 50 MB jika CSV biasa


def write_csv(df: pd.DataFrame, out: Path, name: str) -> Path:
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            has_time = (df[c].dropna().dt.floor("D") != df[c].dropna()).any()
            df[c] = df[c].dt.strftime("%Y-%m-%d %H:%M:%S" if has_time else "%Y-%m-%d")
        elif pd.api.types.is_bool_dtype(df[c]):
            df[c] = df[c].map({True: "true", False: "false"})
    path = out / (f"{name}.csv.gz" if name in GZIP_TABLES else f"{name}.csv")
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n",
              compression="gzip" if name in GZIP_TABLES else None)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate data dummy Retail HQ (50 toko Bali, 2 tahun)")
    ap.add_argument("--config", default=str(ROOT / "config" / "generator.toml"))
    ap.add_argument("--out", default=str(ROOT / "data" / "raw"))
    ap.add_argument("--seed", type=int, default=None, help="override seed di config")
    args = ap.parse_args(argv)

    cfg = tomllib.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.seed is not None:
        cfg["seed"] = args.seed
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(cfg["seed"])
    start, end = cfg["start_date"], cfg["end_date"]
    t0 = time.time()

    def log(msg):
        print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)

    cal = build_calendar(start, end)
    stores = make_stores(cfg, rng)
    suppliers = make_suppliers(rng)
    products = make_products(cfg, rng, suppliers)
    assert len(products) == cfg["n_sku"], f"jumlah SKU {len(products)} != n_sku {cfg['n_sku']}"
    s = pick_stories(stores)
    log("master selesai")

    campaigns = make_campaigns(rng, stores, start, end)
    sales = simulate_sales(cfg, rng, cal, stores, products, campaigns, s)
    log("penjualan selesai")
    sw, assort = sales.pop("_sw"), sales.pop("_assort")

    fixtures = ops.make_fixtures(rng, stores)
    planogram = ops.make_planogram(rng, assort, fixtures, start)
    tables = {
        "dim_store": stores[["store_code", "store_name", "regency", "district", "location_type", "am_name", "ak_name",
                             "store_type", "size_m2", "open_date", "status"]],
        "dim_product": products[["sku", "product_name", "category", "subcategory", "brand", "supplier_id",
                                 "cost_price", "sell_price"]],
        "dim_supplier": suppliers,
        **sales,
        "dim_fixture": fixtures,
        "fact_planogram": planogram,
        "fact_display_audit": ops.make_display_audit(rng, planogram, stores, s, start, end),
        "fact_secondary_display": ops.make_secondary_display(rng, campaigns, assort, stores),
        "fact_purchase_order": ops.make_purchase_orders(rng, sw, products, suppliers, s),
        "fact_dc_shipment": ops.make_dc_shipments(rng, sw, stores, s, end),
    }
    log("supply chain & planogram selesai")

    emp = bo.make_employees(rng, stores, s, start, end)
    tables["dim_employee"] = emp
    tables["fact_shift"] = bo.make_shifts(rng, emp, tables["fact_sales_daily"], s)
    contracts = bo.make_contracts(rng, stores, s)
    tables["dim_contract"] = contracts
    tables["fact_capex_project"] = bo.make_capex(rng, stores, s)
    assets, tickets = bo.make_it(rng, stores, s, start, end)
    tables["dim_it_asset"], tables["fact_it_ticket"] = assets, tickets
    tables["fact_pos_downtime"] = bo.make_pos_downtime(rng, tables["fact_sales_daily"], s)
    members, member_monthly = bo.make_members(rng, cfg, stores, tables["fact_sales_daily"], start, end)
    tables["dim_member"], tables["fact_member_monthly"] = members, member_monthly
    tables["fact_campaign"] = campaigns.drop(columns="uplift")
    (tables["fact_stock_opname"], tables["fact_writeoff"], tables["fact_pos_void"],
     tables["fact_cash_variance"]) = bo.make_loss_prevention(rng, sw, products, tables["fact_sales_daily"], stores, s)
    energy, waste, plastic = bo.make_esg(rng, stores, fixtures, tables["fact_sales_daily"], s)
    tables["fact_energy_monthly"], tables["fact_waste_monthly"], tables["fact_plastic_monthly"] = energy, waste, plastic
    tables["fact_opex_monthly"], tables["fact_budget_monthly"] = bo.make_finance(
        rng, stores, tables["fact_sales_daily"], emp, contracts, energy, campaigns, tickets, start, end)
    log("back office selesai")

    problems = validate(tables, NYEPI)
    if problems:
        print("\nVALIDASI GAGAL:")
        for p in problems:
            print("  -", p)
        return 1
    log("validasi lolos")

    manifest = []
    for name, df in tables.items():
        path = write_csv(df, out, name)
        manifest.append({"table": name, "file": path.name, "rows": len(df), "columns": len(df.columns)})
    pd.DataFrame(manifest).to_csv(out / "_manifest.csv", index=False, lineterminator="\n")
    (out.parent / "_answer_key.md").write_text(answer_key(s), encoding="utf-8")
    log(f"{len(tables)} tabel ditulis ke {out}")
    for m in manifest:
        print(f"  {m['table']:<28} {m['rows']:>10,} baris")
    return 0


if __name__ == "__main__":
    sys.exit(main())
