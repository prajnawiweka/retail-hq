"""Akses BigQuery untuk tool agent: query tetap, parameter aman, hasil ringkas."""
from __future__ import annotations

import datetime as dt
import decimal
from functools import lru_cache

from retailhq_agents.config import settings

MAX_BYTES = 2_000_000_000  # pengaman biaya per query (2 GB); data mart jauh di bawah ini


@lru_cache
def client():
    from google.cloud import bigquery

    s = settings()
    return bigquery.Client(project=s["GCP_PROJECT_ID"], location=s.get("BQ_LOCATION") or None)


def table(name: str) -> str:
    s = settings()
    return f"`{s['GCP_PROJECT_ID']}.{s['BQ_DATASET_MART']}.{name}`"


def _plain(v):
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()[:10]
    if isinstance(v, decimal.Decimal):
        v = float(v)
    if isinstance(v, float):
        return round(v, 4) if abs(v) < 100 else round(v)
    return v


def query(sql: str, **params) -> list[dict]:
    """Jalankan SQL dengan parameter bernama (@nama). Tipe ditebak dari nilai Python."""
    from google.cloud import bigquery

    qp = []
    for k, v in params.items():
        if isinstance(v, dt.date):
            qp.append(bigquery.ScalarQueryParameter(k, "DATE", v))
        elif isinstance(v, bool):
            qp.append(bigquery.ScalarQueryParameter(k, "BOOL", v))
        elif isinstance(v, int):
            qp.append(bigquery.ScalarQueryParameter(k, "INT64", v))
        else:
            qp.append(bigquery.ScalarQueryParameter(k, "STRING", v))
    cfg = bigquery.QueryJobConfig(query_parameters=qp, maximum_bytes_billed=MAX_BYTES)
    rows = client().query(sql, job_config=cfg).result()
    return [{k: _plain(v) for k, v in r.items()} for r in rows]


@lru_cache
def month_bounds() -> tuple[dt.date, dt.date]:
    r = query(f"select min(month) as lo, max(month) as hi from {table('mart_store_monthly')}")[0]
    return dt.date.fromisoformat(r["lo"]), dt.date.fromisoformat(r["hi"])


def _add_months(d: dt.date, n: int) -> dt.date:
    m = d.month - 1 + n
    return dt.date(d.year + m // 12, m % 12 + 1, 1)


def period(start_month: str = "", end_month: str = "") -> dict:
    """Ubah 'YYYY-MM' jadi rentang tanggal. Default: 12 bulan terakhir yang ada datanya.

    Juga mengembalikan periode pembanding tahun lalu (geser 12 bulan).
    """
    lo, hi = month_bounds()

    def parse(s: str) -> dt.date | None:
        s = (s or "").strip()[:7]
        if not s:
            return None
        try:
            y, m = s.split("-")
            return dt.date(int(y), int(m), 1)
        except ValueError:
            raise ValueError(f"Format bulan harus YYYY-MM, bukan '{s}'")

    end = parse(end_month) or hi
    start = parse(start_month) or _add_months(end, -11)
    start, end = max(start, lo), min(end, hi)
    if start > end:
        start, end = end, start
    return {
        "start": start,
        "end": end,
        "py_start": _add_months(start, -12),
        "py_end": _add_months(end, -12),
        "label": f"{start:%Y-%m} s.d. {end:%Y-%m}",
    }


def growth(cur, prev):
    if cur is None or not prev:
        return None
    return round(cur / prev - 1, 4)
