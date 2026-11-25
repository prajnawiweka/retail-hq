"""Potongan SQL dan helper yang dipakai bersama oleh tool department."""
from __future__ import annotations

from retailhq_agents import bq

# Filter toko opsional; nilai kosong = semua.
STORE_FILTER = "(@regency = '' or regency = @regency) and (@am_name = '' or am_name = @am_name)"


def params(p: dict, regency: str = "", am_name: str = "", **extra) -> dict:
    return {
        "start": p["start"], "end": p["end"], "py_start": p["py_start"], "py_end": p["py_end"],
        "regency": (regency or "").strip(), "am_name": (am_name or "").strip(), **extra,
    }


def scope(p: dict, regency: str = "", am_name: str = "") -> dict:
    out = {"periode": p["label"], "pembanding": f"{p['py_start']:%Y-%m} s.d. {p['py_end']:%Y-%m}"}
    if regency:
        out["kabupaten"] = regency
    if am_name:
        out["am_name"] = am_name
    return out


def safe(fn):
    """Bungkus tool: error dikembalikan sebagai teks supaya agent bisa menjelaskan, bukan crash."""
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:  # noqa: BLE001 - error BigQuery/jaringan diteruskan ke agent
            return {"error": f"Query gagal: {type(e).__name__}: {str(e)[:300]}"}

    return wrapper


def periode_data() -> dict:
    """Rentang bulan yang tersedia di data, dan periode default (12 bulan terakhir)."""
    lo, hi = bq.month_bounds()
    p = bq.period()
    return {"bulan_pertama": f"{lo:%Y-%m}", "bulan_terakhir": f"{hi:%Y-%m}", "periode_default": p["label"]}
