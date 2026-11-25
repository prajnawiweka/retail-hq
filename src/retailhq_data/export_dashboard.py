"""Ekspor data mart BigQuery ke dashboard HTML.

Pakai:  uv run export-dashboard

Hasil:
  dashboard/data.json    data mentah dashboard (dibaca index.html saat dev)
  dashboard/dist/index.html  satu file HTML siap dibuka/dibagikan (data sudah ditanam)

Semua rasio dihitung ulang di browser dari jumlah (SUM/SUM), sama seperti
Looker Studio, supaya filter dan rentang bulan tetap benar.
Login dulu sekali:  gcloud auth application-default login
"""
from __future__ import annotations

import datetime as dt
import decimal
import json
import sys
from pathlib import Path

from retailhq_data.load_bq import read_env

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "dashboard"
PLACEHOLDER = "/*__DATA__*/null"

QUERIES: dict[str, str] = {
    "stores": """
        select store_code, store_name, regency, location_type, store_type,
               am_name, ak_name, size_m2, open_date
        from `{mart}.dim_store`
        order by store_code""",
    "store_monthly": """
        select month, store_code, open_days, net_sales, target_sales, gross_profit, std,
               rent, salary, utilities, maintenance, promo_cost, it_cost, other_cost,
               total_opex, budget_opex, sku_weeks, oos_sku_weeks, soh_zero_sku_weeks,
               compliant_items, audited_items
        from `{mart}.mart_store_monthly`
        order by month, store_code""",
    "daily": """
        select d.sales_date, s.regency, sum(d.net_sales) as net_sales,
               sum(d.target_spd) as target_sales, max(d.event) as event
        from `{mart}.fct_sales_store_daily` d
        join `{mart}.dim_store` s using (store_code)
        group by 1, 2
        order by 1, 2""",
    "category_monthly": """
        select month, store_code, category, net_sales, gross_profit
        from `{mart}.mart_category_monthly`
        order by month, store_code, category""",
    "campaigns": """
        select campaign_id, campaign_name, target_category, channel, start_date, end_date,
               cost, sales_during, incremental_sales, incremental_gross_profit, uplift_pct, roi
        from `{mart}.mart_campaign_performance`
        order by start_date""",
    "planogram_monthly": """
        select month, store_code, audited_items, compliant_items
        from `{mart}.mart_planogram_compliance_monthly`
        order by month, store_code""",
    "oos_sku_monthly": """
        select month, sku, product_name, category, supplier_id,
               stores_carrying, stores_oos, stores_soh_zero, est_lost_sales
        from `{mart}.mart_oos_sku_monthly`
        where stores_oos > 0
        order by month, sku""",
    "supplier_monthly": """
        select month, supplier_id, supplier_name, po_lines, on_time_lines,
               qty_ordered, qty_received
        from `{mart}.mart_supplier_monthly`
        order by month, supplier_id""",
    "dc_monthly": """
        select month, store_code, shipments, on_time_shipments,
               qty_requested, qty_shipped, delivery_cost
        from `{mart}.mart_dc_store_monthly`
        order by month, store_code""",
}


def _plain(v):
    """Ubah nilai BigQuery ke tipe JSON; uang dibulatkan agar file kecil."""
    if v is None:
        return None
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()[:10]
    if isinstance(v, decimal.Decimal):
        v = float(v)
    if isinstance(v, float):
        return round(v, 4) if abs(v) < 1000 else round(v)
    return v


def fetch(client, sql: str) -> dict:
    rows = list(client.query(sql).result())
    cols = list(rows[0].keys()) if rows else []
    return {"cols": cols, "rows": [[_plain(r[c]) for c in cols] for r in rows]}


def main() -> None:
    from google.cloud import bigquery

    env = read_env(ROOT / ".env")
    project = env.get("GCP_PROJECT_ID")
    if not project:
        sys.exit("GCP_PROJECT_ID belum diisi di .env")
    mart = f"{project}.{env.get('BQ_DATASET_MART', 'mart')}"
    client = bigquery.Client(project=project, location=env.get("BQ_LOCATION") or None)

    data: dict = {"generated_at": dt.datetime.now().isoformat(timespec="seconds")}
    for name, sql in QUERIES.items():
        data[name] = fetch(client, sql.format(mart=mart))
        print(f"  {name:<18} {len(data[name]['rows']):>6} baris")

    OUT_DIR.mkdir(exist_ok=True)
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    (OUT_DIR / "data.json").write_text(payload, encoding="utf-8")

    tpl_path = OUT_DIR / "index.html"
    if not tpl_path.exists():
        print("Selesai: dashboard/data.json (index.html belum ada, dist dilewati)")
        return
    template = tpl_path.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        sys.exit(f"Placeholder {PLACEHOLDER} tidak ditemukan di dashboard/index.html")
    dist = OUT_DIR / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "index.html").write_text(
        template.replace(PLACEHOLDER, payload.replace("</", "<\\/")), encoding="utf-8"
    )
    kb = (dist / "index.html").stat().st_size / 1024
    print(f"Selesai: dashboard/data.json dan dashboard/dist/index.html ({kb:,.0f} KB)")


if __name__ == "__main__":
    main()
