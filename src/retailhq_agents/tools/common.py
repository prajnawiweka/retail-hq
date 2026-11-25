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
    """Mode data (dummy/asli), rentang bulan yang tersedia, periode default (12 bulan terakhir),
    dan department yang datanya belum diunggah."""
    lo, hi = bq.month_bounds()
    p = bq.period()
    st = bq.data_state()
    return {"mode_data": st.get("mode", "dummy"), "dimuat": st.get("loaded_at"),
            "bulan_pertama": f"{lo:%Y-%m}", "bulan_terakhir": f"{hi:%Y-%m}", "periode_default": p["label"],
            "department_tanpa_data": st.get("department_tanpa_data", [])}


def _order(urutan: str) -> str:
    u = (urutan or "").lower()
    return "asc" if u.startswith("terendah") or u == "asc" else "desc"


def store_ranking(
    metrics: dict[str, str],
    metric: str,
    urutan: str = "tertinggi",
    limit: int = 10,
    start_month: str = "",
    end_month: str = "",
    regency: str = "",
    am_name: str = "",
    peer_by: str = "",
) -> dict:
    """Ranking toko di mart_store_monthly untuk satu metrik, plus semua metrik lain dan rata-rata jaringan.

    metrics: nama -> ekspresi agregat SQL (misal "safe_divide(sum(exits), sum(headcount_end))").
    peer_by: kolom toko (misal 'store_type') untuk menghitung rasio terhadap rata-rata toko sejenis.
    """
    if metric not in metrics:
        raise ValueError(f"metric harus salah satu dari: {', '.join(metrics)}")
    p = bq.period(start_month, end_month)
    cols = ",\n".join(f"{expr} as {name}" for name, expr in metrics.items())
    peer = ""
    if peer_by:
        peer = (f", safe_divide({metric}, avg({metric}) over (partition by {peer_by})) - 1 "
                f"as {metric}_vs_toko_sejenis")
    sql = f"""
        with t as (
          select store_code, any_value(regency) as regency, any_value(am_name) as am_name,
                 any_value(store_type) as store_type, any_value(location_type) as location_type,
                 {cols}
          from {bq.table('mart_store_monthly')}
          where month between @start and @end and {STORE_FILTER}
          group by store_code)
        select * {peer} from t
        order by {metric} {_order(urutan)} nulls last
        limit @lim"""
    avg_sql = f"""select {cols} from {bq.table('mart_store_monthly')}
                  where month between @start and @end and {STORE_FILTER}"""
    q = params(p, regency, am_name, lim=max(1, min(int(limit), 50)))
    return {
        **scope(p, regency, am_name),
        "metric": metric,
        "urutan": urutan,
        "rata_rata_jaringan": bq.query(avg_sql, **q)[0],
        "toko": bq.query(sql, **q),
    }
