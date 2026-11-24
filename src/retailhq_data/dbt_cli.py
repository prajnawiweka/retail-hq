"""Jalankan dbt dengan .env project dan folder dbt/ otomatis.

Pakai:  uv run dbt-rhq debug      (cek koneksi)
        uv run dbt-rhq build      (seed + model + test)
        uv run dbt-rhq build --select marts
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .load_bq import ROOT, read_env


def main() -> int:
    for k, v in read_env(ROOT / ".env").items():
        if v:
            os.environ.setdefault(k, v)
    if not os.environ.get("GCP_PROJECT_ID") or os.environ["GCP_PROJECT_ID"] == "isi-project-id-kamu":
        print("GCP_PROJECT_ID di file .env belum diisi.")
        return 1
    dbt_dir = str(ROOT / "dbt")
    args = sys.argv[1:] or ["build"]
    if args[0] not in ("deps", "clean", "init"):
        args += ["--project-dir", dbt_dir, "--profiles-dir", dbt_dir]
    from dbt.cli.main import dbtRunner

    res = dbtRunner().invoke(args)
    return 0 if res.success else 1


if __name__ == "__main__":
    sys.exit(main())
