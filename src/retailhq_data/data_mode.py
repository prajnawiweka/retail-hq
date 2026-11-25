"""Data Mode: ganti data dummy dengan data asli, atau kembali ke dummy.

Pakai:
  uv run data-mode status                    mode aktif (dummy/asli), periode, tabel yang kosong
  uv run data-mode template                  buat template kosong di data/templates/ (CSV + 1 file Excel)
  uv run data-mode validate <folder|file.xlsx>   cek data asli tanpa mengubah apa pun
  uv run data-mode load <folder|file.xlsx>   validasi -> muat ke BigQuery -> dbt -> dashboard
  uv run data-mode reset                     kembali ke data dummy (data/raw)

Format input: satu file per tabel bernama <tabel>.csv / .csv.gz / .xlsx di satu folder,
ATAU satu file Excel dengan sheet bernama <tabel>. Kolom dan tipe mengikuti config/data_contract.json.
Tabel wajib: dim_store, dim_product, fact_sales_daily, fact_sales_category_daily. Tabel lain boleh
tidak ada; tabel itu dimuat kosong dan agent department terkait akan bilang datanya belum diunggah.

PERHATIAN: load dan reset MENIMPA dataset raw di BigQuery (dan mart hasil dbt).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd

from .load_bq import ROOT, read_env

CONTRACT_PATH = ROOT / "config" / "data_contract.json"
STATE_PATH = ROOT / "data" / "mode.json"
REAL_DIR = ROOT / "data" / "real"
DUMMY_DIR = ROOT / "data" / "raw"
TEMPLATE_DIR = ROOT / "data" / "templates"

BOOL_MAP = {"true": "true", "false": "false", "1": "true", "0": "false", "ya": "true", "tidak": "false",
            "yes": "true", "no": "false", "y": "true", "n": "false", "t": "true", "f": "false"}

# Department -> tabel yang dibutuhkan (dipakai agent untuk tahu data mana yang kosong).
DEPT_TABLES = {
    "operation": ["fact_sales_daily"],
    "merchandise": ["fact_sales_category_daily", "fact_display_audit"],
    "finance": ["fact_opex_monthly"],
    "supply_chain": ["fact_stock_weekly", "fact_purchase_order"],
    "dc": ["fact_dc_shipment"],
    "hr": ["dim_employee", "fact_shift"],
    "loss_prevention": ["fact_stock_opname", "fact_writeoff", "fact_pos_void", "fact_cash_variance"],
    "it": ["fact_it_ticket", "fact_pos_downtime", "dim_it_asset"],
    "marketing": ["fact_campaign", "fact_member_monthly"],
    "esg": ["fact_energy_monthly", "fact_waste_monthly", "fact_plastic_monthly"],
    "legal": ["dim_contract"],
    "store_dev": ["fact_capex_project"],
}


def contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def read_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"mode": "dummy", "catatan": "belum pernah dijalankan; diasumsikan data dummy"}


def _norm_col(c: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", re.sub(r"\s+", "_", str(c).strip().lower()))


# ---------------------------------------------------------------- input
def read_input(src: Path, tables: dict) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Baca folder (file per tabel) atau satu .xlsx (sheet per tabel). Semua kolom dibaca sebagai teks."""
    try:
        return _read_input(src, tables)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 - file rusak / format salah
        raise SystemExit(f"Gagal membaca {src}: {type(e).__name__}: {e}. Pastikan file CSV/Excel tidak rusak.")


def _read_input(src: Path, tables: dict) -> tuple[dict[str, pd.DataFrame], list[str]]:
    found: dict[str, pd.DataFrame] = {}
    notes: list[str] = []
    names = {t.lower(): t for t in tables}
    if src.is_file() and src.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        sheets = pd.read_excel(src, sheet_name=None, dtype=str, keep_default_na=False, na_values=[""])
        for sheet, df in sheets.items():
            t = names.get(sheet.strip().lower())
            if t:
                found[t] = df
            else:
                notes.append(f"sheet '{sheet}' diabaikan (bukan nama tabel di kontrak)")
    elif src.is_dir():
        for f in sorted(src.iterdir()):
            stem = f.name.lower()
            for ext in (".csv.gz", ".csv", ".xlsx", ".xls"):
                if stem.endswith(ext):
                    stem = stem[: -len(ext)]
                    break
            else:
                continue
            t = names.get(stem)
            if not t:
                if not f.name.startswith(("_", ".")):
                    notes.append(f"file '{f.name}' diabaikan (bukan nama tabel di kontrak)")
                continue
            if f.name.lower().endswith((".xlsx", ".xls")):
                found[t] = pd.read_excel(f, dtype=str, keep_default_na=False, na_values=[""])
            else:
                found[t] = pd.read_csv(f, dtype=str, keep_default_na=False, na_values=[""])
    else:
        raise SystemExit(f"Input tidak ditemukan atau format tidak didukung: {src}")
    return found, notes


# ---------------------------------------------------------------- validasi
def _parse_dates(s: pd.Series, with_time: bool) -> pd.Series:
    s = s.str.strip()
    iso = pd.to_datetime(s, errors="coerce", format="ISO8601")
    if iso.isna().sum() > s.notna().sum() * 0.5:  # kebanyakan bukan ISO: coba format Indonesia dd/mm/yyyy
        iso = iso.fillna(pd.to_datetime(s, errors="coerce", dayfirst=True))
    fmt = "%Y-%m-%d %H:%M:%S" if with_time else "%Y-%m-%d"
    return iso.dt.strftime(fmt)


def normalize(table: str, df: pd.DataFrame, spec: dict) -> tuple[pd.DataFrame, list[str], list[str]]:
    err: list[str] = []
    warn: list[str] = []
    df = df.copy()
    df.columns = [_norm_col(c) for c in df.columns]
    df = df.dropna(how="all")
    cols = [c["name"] for c in spec["columns"]]
    keys = set(spec.get("primary_key", [])) | {"store_code", "sku", "supplier_id", "employee_id", "member_id"} & set(cols)
    extra = [c for c in df.columns if c not in cols]
    if extra:
        warn.append(f"kolom tambahan diabaikan: {', '.join(extra)}")
    missing = [c for c in cols if c not in df.columns]
    miss_keys = [c for c in missing if c in keys]
    if miss_keys:
        err.append(f"kolom kunci wajib tidak ada: {', '.join(miss_keys)}")
    if missing and not miss_keys:
        warn.append(f"kolom tidak ada, diisi kosong (metrik terkait tidak bisa dihitung): {', '.join(missing)}")
    for c in missing:
        df[c] = pd.NA
    df = df[cols]

    for c in spec["columns"]:
        name, typ = c["name"], c["type"]
        s = df[name]
        filled = s.notna() & (s.astype(str).str.strip() != "")
        if typ in ("DATE", "DATETIME"):
            out = _parse_dates(s.astype("string"), typ == "DATETIME")
            bad = filled & out.isna()
        elif typ in ("INT64", "FLOAT64"):
            txt = s.astype("string").str.strip().str.replace(r"^Rp\.?\s*", "", regex=True).str.replace(" ", "")
            # format Indonesia 1.234.567,89 -> 1234567.89 (hanya kalau ada koma desimal atau titik ribuan)
            comma_dec = txt.str.contains(r",\d+$", na=False)
            thousands = txt.str.contains(r"^-?\d{1,3}(?:\.\d{3})+$", na=False)
            # titik ribuan hanya ditafsirkan di kolom bilangan bulat (rupiah, qty); di kolom desimal 12.345 tetap 12.345
            indo = comma_dec | (thousands if typ == "INT64" else False)
            txt = txt.where(~indo, txt.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
            num = pd.to_numeric(txt, errors="coerce")
            bad = filled & num.isna()
            if typ == "INT64":
                frac = num.notna() & (num != num.round())
                if frac.any():
                    warn.append(f"{name}: {frac.sum()} nilai desimal dibulatkan ke bilangan bulat")
                out = num.round().astype("Int64").astype("string")
            else:
                out = num.astype("string")
            neg = (num < 0).sum()
            if neg:
                warn.append(f"{name}: {neg} nilai negatif")
        elif typ == "BOOL":
            out = s.astype("string").str.strip().str.lower().map(BOOL_MAP)
            bad = filled & out.isna()
        else:
            out = s.astype("string").str.strip()
            bad = pd.Series(False, index=s.index)
        if bad.any():
            sample = ", ".join(map(str, s[bad].head(3).tolist()))
            err.append(f"{name} ({typ}): {bad.sum()} nilai tidak valid, contoh: {sample}")
        df[name] = out

    pk = spec.get("primary_key") or []
    if pk and not miss_keys:
        nulls = df[pk].isna().any(axis=1).sum()
        if nulls:
            err.append(f"{nulls} baris dengan kunci {pk} kosong")
        dup = df.duplicated(pk).sum()
        if dup:
            err.append(f"{dup} baris duplikat pada kunci {pk}")
    if df.empty:
        warn.append("tabel kosong")
    return df, err, warn


def validate_all(src: Path) -> tuple[dict[str, pd.DataFrame], dict[str, list[str]], dict[str, list[str]], list[str]]:
    c = contract()
    tables = c["tables"]
    raw, notes = read_input(src, tables)
    data: dict[str, pd.DataFrame] = {}
    errors: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}
    for t, spec in tables.items():
        if t not in raw:
            if spec["required"]:
                errors[t] = ["tabel wajib tidak ditemukan"]
            continue
        df, e, w = normalize(t, raw[t], spec)
        data[t] = df
        if e:
            errors[t] = e
        if w:
            warnings[t] = w
    # relasi antar tabel (hanya kalau tabel referensi ikut diunggah)
    for fk in c["foreign_keys"]:
        col, ref, rcol = fk["column"], fk["ref_table"], fk["ref_column"]
        if ref not in data:
            continue
        valid = set(data[ref][rcol].dropna())
        for t, df in data.items():
            if t == ref or col not in df.columns:
                continue
            bad = df[col].notna() & ~df[col].isin(valid)
            if bad.any():
                errors.setdefault(t, []).append(
                    f"{col}: {bad.sum()} baris merujuk ke {ref} yang tidak ada, contoh: {', '.join(df.loc[bad, col].astype(str).unique()[:3])}"
                )
    # rekonsiliasi penjualan harian vs kategori (dbt juga mengetes ini)
    if "fact_sales_daily" in data and "fact_sales_category_daily" in data and not errors.get("fact_sales_daily"):
        sd = data["fact_sales_daily"].assign(v=lambda d: pd.to_numeric(d["net_sales"]))
        cd = data["fact_sales_category_daily"].assign(v=lambda d: pd.to_numeric(d["net_sales"]))
        a = sd.groupby(["sales_date", "store_code"])["v"].sum()
        b = cd.groupby(["sales_date", "store_code"])["v"].sum()
        j = pd.concat([a, b], axis=1, keys=["toko", "kategori"]).fillna(0)
        off = ((j["toko"] - j["kategori"]).abs() > j["toko"].abs() * 0.001 + 1).sum()
        if off:
            warnings.setdefault("fact_sales_category_daily", []).append(
                f"{off} hari-toko total kategori tidak sama dengan fact_sales_daily (tes dbt rekonsiliasi akan gagal)"
            )
    return data, errors, warnings, notes


def print_report(data, errors, warnings, notes) -> None:
    tables = contract()["tables"]
    print(f"\n{'Tabel':<28}{'Baris':>10}  Status")
    for t, spec in tables.items():
        if t in data:
            st = "ERROR" if t in errors else ("peringatan" if t in warnings else "ok")
            print(f"{t:<28}{len(data[t]):>10,}  {st}")
        else:
            print(f"{t:<28}{'-':>10}  {'TIDAK ADA (wajib)' if spec['required'] else 'tidak diunggah, dimuat kosong'}")
    for title, d in (("ERROR (harus diperbaiki)", errors), ("Peringatan", warnings)):
        if d:
            print(f"\n{title}:")
            for t, msgs in d.items():
                for m in msgs:
                    print(f"  - {t}: {m}")
    for n in notes:
        print(f"  - catatan: {n}")


# ---------------------------------------------------------------- muat ke BigQuery
def write_folder(data: dict[str, pd.DataFrame], out: Path) -> dict[str, int]:
    tables = contract()["tables"]
    out.mkdir(parents=True, exist_ok=True)
    rows = {}
    for t, spec in tables.items():
        df = data.get(t, pd.DataFrame(columns=[c["name"] for c in spec["columns"]]))
        df.to_csv(out / f"{t}.csv", index=False)
        rows[t] = len(df)
    return rows


def bq_load(folder: Path, files: dict[str, str] | None = None) -> None:
    from google.cloud import bigquery

    env = read_env(ROOT / ".env")
    project, location = env["GCP_PROJECT_ID"], env.get("BQ_LOCATION", "asia-southeast2")
    dataset = env.get("BQ_DATASET_RAW", "raw")
    client = bigquery.Client(project=project, location=location)
    ds = bigquery.Dataset(f"{project}.{dataset}")
    ds.location = location
    client.create_dataset(ds, exists_ok=True)
    t0 = time.time()
    for t, spec in contract()["tables"].items():
        path = folder / (files or {}).get(t, f"{t}.csv")
        schema = [bigquery.SchemaField(c["name"], c["type"]) for c in spec["columns"]]
        cfg = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV, skip_leading_rows=1, schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        with open(path, "rb") as f:
            client.load_table_from_file(f, f"{project}.{dataset}.{t}", job_config=cfg).result()
        n = client.get_table(f"{project}.{dataset}.{t}").num_rows
        print(f"[{time.time() - t0:6.1f}s] {t:<28} {n:>10,} baris", flush=True)


def run_dbt(report_date: str | None) -> bool:
    """seed + run, lalu test terpisah: tes yang gagal tidak menghentikan pembuatan mart."""
    for k, v in read_env(ROOT / ".env").items():
        if v:
            os.environ.setdefault(k, v)
    from dbt.cli.main import dbtRunner

    base = ["--project-dir", str(ROOT / "dbt"), "--profiles-dir", str(ROOT / "dbt")]
    if report_date:
        base += ["--vars", json.dumps({"report_date": report_date})]
    r = dbtRunner()
    for cmd in (["seed"], ["run"]):
        if not r.invoke(cmd + base).success:
            print(f"dbt {cmd[0]} gagal. Lihat pesan di atas.")
            return False
    if not r.invoke(["test"] + base).success:
        print("\nPERINGATAN: sebagian tes dbt gagal (lihat di atas). Mart tetap dibuat, tapi cek kualitas data.")
    return True


def export_dashboard() -> None:
    try:
        from .export_dashboard import main as export

        export()
    except SystemExit as e:  # export memakai sys.exit untuk pesan error
        print(f"Dashboard tidak diperbarui: {e}")


def save_state(mode: str, source: str, rows: dict[str, int], data_dates: tuple[str, str], report_date: str) -> dict:
    empty = sorted(t for t, n in rows.items() if n == 0)
    state = {
        "mode": mode,
        "source": source,
        "loaded_at": dt.datetime.now().isoformat(timespec="seconds"),
        "periode": {"mulai": data_dates[0], "akhir": data_dates[1]},
        "report_date": report_date,
        "tabel": rows,
        "tabel_kosong": empty,
        "department_tanpa_data": sorted(d for d, ts in DEPT_TABLES.items() if all(t in empty for t in ts)),
    }
    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
    return state


def confirm(msg: str, yes: bool) -> bool:
    if yes:
        return True
    print(msg)
    return input("Ketik YA untuk lanjut: ").strip().upper() == "YA"


# ---------------------------------------------------------------- perintah
def cmd_status(_args) -> int:
    s = read_state()
    print(json.dumps({k: v for k, v in s.items() if k != "tabel"}, indent=1, ensure_ascii=False))
    return 0


def cmd_template(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    c = contract()
    lines = ["# Kontrak data Retail HQ", "", "Satu file per tabel (`<tabel>.csv` / `.xlsx`) atau satu Excel dengan sheet bernama tabel.",
             "Tanggal `YYYY-MM-DD` (dd/mm/yyyy juga diterima), uang dalam rupiah, boolean true/false.", ""]
    with pd.ExcelWriter(out / "retail_hq_template.xlsx") as xw:
        for t, spec in c["tables"].items():
            cols = [x["name"] for x in spec["columns"]]
            pd.DataFrame(columns=cols).to_csv(out / f"{t}.csv", index=False)
            pd.DataFrame(columns=cols).to_excel(xw, sheet_name=t[:31], index=False)
            lines += [f"## {t}{' (WAJIB)' if spec['required'] else ''}", spec["description"],
                      f"Kunci unik: {', '.join(spec['primary_key']) or '-'}", "",
                      "| kolom | tipe |", "|---|---|"] + [f"| {x['name']} | {x['type']} |" for x in spec["columns"]] + [""]
    (out / "KONTRAK_DATA.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Template dibuat di {out}: 32 CSV kosong, retail_hq_template.xlsx, KONTRAK_DATA.md")
    return 0


def cmd_validate(args) -> int:
    data, errors, warnings, notes = validate_all(Path(args.source))
    print_report(data, errors, warnings, notes)
    if errors:
        print(f"\nTIDAK LOLOS: {sum(map(len, errors.values()))} error. Perbaiki lalu jalankan validate lagi.")
        return 1
    print("\nLOLOS. Data siap dimuat dengan: uv run data-mode load " + args.source)
    return 0


def cmd_load(args) -> int:
    src = Path(args.source)
    data, errors, warnings, notes = validate_all(src)
    print_report(data, errors, warnings, notes)
    if errors:
        print("\nDibatalkan: masih ada error. Tidak ada yang diubah di BigQuery.")
        return 1
    if not confirm("\nData asli akan MENIMPA dataset raw dan mart di BigQuery (data dummy bisa dikembalikan "
                   "dengan `uv run data-mode reset`).", args.yes):
        print("Dibatalkan.")
        return 1
    rows = write_folder(data, REAL_DIR)
    sd = pd.to_datetime(data["fact_sales_daily"]["sales_date"])
    dates = (f"{sd.min():%Y-%m-%d}", f"{sd.max():%Y-%m-%d}")
    print(f"\n1/3 Memuat ke BigQuery (periode {dates[0]} s.d. {dates[1]})")
    bq_load(REAL_DIR)
    print("\n2/3 Membangun mart dengan dbt")
    if not run_dbt(dates[1]):
        return 1
    state = save_state("asli", str(src.resolve()), rows, dates, dates[1])
    print("\n3/3 Memperbarui dashboard")
    export_dashboard()
    print(f"\nSelesai. Mode: DATA ASLI. Department tanpa data: {', '.join(state['department_tanpa_data']) or '-'}")
    print("Jalankan ulang bot Telegram (Ctrl+C lalu uv run rhq-bot) supaya agent membaca data baru.")
    return 0


def cmd_reset(args) -> int:
    man = DUMMY_DIR / "_manifest.csv"
    if not man.exists():
        print("data/raw belum ada. Buat dulu data dummy: uv run generate-data")
        return 1
    if not confirm("Dataset raw dan mart di BigQuery akan dikembalikan ke data DUMMY.", args.yes):
        print("Dibatalkan.")
        return 1
    m = pd.read_csv(man)
    files = dict(zip(m["table"], m["file"]))
    print("1/3 Memuat data dummy ke BigQuery")
    bq_load(DUMMY_DIR, files)
    print("\n2/3 Membangun mart dengan dbt")
    if not run_dbt(None):
        return 1
    sd = pd.read_csv(DUMMY_DIR / files["fact_sales_daily"], usecols=["sales_date"])["sales_date"]
    save_state("dummy", "data/raw (generate-data)", dict(zip(m["table"], m["rows"].astype(int))),
               (sd.min(), sd.max()), "2026-10-31")
    print("\n3/3 Memperbarui dashboard")
    export_dashboard()
    print("\nSelesai. Mode: DUMMY. Jalankan ulang bot Telegram supaya agent membaca data ini.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="data-mode", description="Ganti data dummy <-> data asli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    t = sub.add_parser("template")
    t.add_argument("out", nargs="?", default=str(TEMPLATE_DIR))
    v = sub.add_parser("validate")
    v.add_argument("source", help="folder berisi <tabel>.csv/.xlsx, atau satu file .xlsx (sheet per tabel)")
    ld = sub.add_parser("load")
    ld.add_argument("source")
    ld.add_argument("--yes", action="store_true", help="lewati konfirmasi")
    r = sub.add_parser("reset")
    r.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)
    return {"status": cmd_status, "template": cmd_template, "validate": cmd_validate,
            "load": cmd_load, "reset": cmd_reset}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
