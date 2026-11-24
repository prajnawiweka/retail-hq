"""Muat CSV di data/raw ke dataset BigQuery (default: raw).

Pakai:  uv run load-bq                     (semua tabel)
        uv run load-bq --tables dim_store fact_sales_daily
        uv run load-bq --dry-run           (cek skema saja, tanpa upload)

Login dulu sekali:  gcloud auth application-default login
Tabel ditimpa (WRITE_TRUNCATE), jadi aman dijalankan ulang, misalnya
setelah tabel kedaluwarsa 60 hari di BigQuery Sandbox.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATETIME_COLS = {"opened_at", "resolved_at"}
DATE_COLS = {"month", "week_start"}


def read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.split("#", 1)[0].strip().strip('"').strip("'")
    for k in list(env):
        env[k] = os.environ.get(k, env[k])
    return env


def infer_schema(path: Path) -> list[tuple[str, str]]:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    schema = []
    for col in df.columns:
        s = df[col].dropna()
        if col in DATETIME_COLS:
            t = "DATETIME"
        elif col in DATE_COLS or col.endswith("_date") or col.startswith("effective_"):
            t = "DATE"
        elif len(s) and s.isin(["true", "false"]).all():
            t = "BOOL"
        elif len(s) and s.str.fullmatch(r"-?\d+").all():
            t = "INT64"
        elif len(s) and pd.to_numeric(s, errors="coerce").notna().all():
            t = "FLOAT64"
        else:
            t = "STRING"
        schema.append((col, t))
    return schema


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Load data/raw ke BigQuery")
    ap.add_argument("--data", default=str(ROOT / "data" / "raw"))
    ap.add_argument("--dataset", default=None, help="default: BQ_DATASET_RAW di .env, atau raw")
    ap.add_argument("--tables", nargs="*", help="hanya tabel tertentu")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    env = read_env(ROOT / ".env")
    project = env.get("GCP_PROJECT_ID", "")
    location = env.get("BQ_LOCATION", "asia-southeast2")
    dataset = args.dataset or env.get("BQ_DATASET_RAW", "raw")
    if not project or project == "isi-project-id-kamu":
        print("GCP_PROJECT_ID di file .env belum diisi.")
        return 1

    data = Path(args.data)
    manifest = pd.read_csv(data / "_manifest.csv")
    if args.tables:
        unknown = set(args.tables) - set(manifest["table"])
        if unknown:
            print(f"Tabel tidak dikenal: {sorted(unknown)}")
            return 1
        manifest = manifest[manifest["table"].isin(args.tables)]

    if args.dry_run:
        for r in manifest.itertuples():
            print(r.table, infer_schema(data / r.file))
        return 0

    from google.api_core.exceptions import GoogleAPIError
    from google.auth.exceptions import DefaultCredentialsError
    from google.cloud import bigquery

    try:
        client = bigquery.Client(project=project, location=location)
        ds = bigquery.Dataset(f"{project}.{dataset}")
        ds.location = location
        client.create_dataset(ds, exists_ok=True)
    except DefaultCredentialsError:
        print("Belum login. Jalankan: gcloud auth application-default login")
        return 1
    except GoogleAPIError as e:
        print(f"Gagal membuat dataset {project}.{dataset}: {e}")
        return 1
    print(f"Dataset {project}.{dataset} ({location}) siap. Memuat {len(manifest)} tabel...")

    failed = []
    t0 = time.time()
    for r in manifest.itertuples():
        path = data / r.file
        schema = [bigquery.SchemaField(c, t) for c, t in infer_schema(path)]
        cfg = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV, skip_leading_rows=1, schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        table_id = f"{project}.{dataset}.{r.table}"
        try:
            with open(path, "rb") as f:
                job = client.load_table_from_file(f, table_id, job_config=cfg)
            job.result()
            n = client.get_table(table_id).num_rows
            ok = "OK " if n == r.rows else "BEDA"
            if n != r.rows:
                failed.append(r.table)
            print(f"[{time.time() - t0:6.1f}s] {ok} {r.table:<28} {n:>10,} baris (file {r.rows:,})", flush=True)
        except GoogleAPIError as e:
            failed.append(r.table)
            print(f"[{time.time() - t0:6.1f}s] GAGAL {r.table}: {e}", flush=True)

    if failed:
        print(f"\n{len(failed)} tabel bermasalah: {failed}. Jalankan ulang: uv run load-bq --tables {' '.join(failed)}")
        return 1
    print(f"\nSelesai. Semua {len(manifest)} tabel cocok dengan jumlah baris file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
