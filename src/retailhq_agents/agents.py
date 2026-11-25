"""Definisi agent: GM (koordinator) + 12 department.

GM memanggil agent department sebagai tool (AgentTool), hanya yang relevan dengan pertanyaan,
lalu menyusun jawaban gabungan. Agent department hanya bisa membaca data lewat tool BigQuery
yang sudah ditentukan (tidak menulis SQL bebas).
"""
from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from retailhq_agents.config import settings
from retailhq_agents.tools import (
    dc, esg, finance, hr, it, legal, loss_prevention, marketing, merchandise, operation, store_dev, supply_chain,
)
from retailhq_agents.tools.common import periode_data

DUMMY_CONTEXT = """
Konteks perusahaan: Retail HQ, jaringan 50 minimarket fiktif di Bali (8 kabupaten), 300 SKU,
25 supplier, 1 DC di Denpasar. Data simulasi Nov 2024 s.d. Okt 2026."""

DEFINITIONS = """
Struktur: Area Manager (AM) membawahi beberapa toko, Area Koordinator (AK) membawahi beberapa AM.
Definisi: SPD = net sales per hari buka per toko; STD = jumlah struk; AMB = net sales / STD;
achievement = net sales / target; EBITDA = gross profit - opex; OOS = SKU ditandai habis di toko;
SOH 0 = stok sistem nol (tidak selalu sama dengan OOS).
"""


def context() -> str:
    """Konteks data untuk instruksi agent, mengikuti mode data aktif (dummy atau asli)."""
    from retailhq_agents.bq import data_state

    st = data_state()
    if st.get("mode") != "asli":
        return DUMMY_CONTEXT + DEFINITIONS
    per = st.get("periode", {})
    rows = st.get("tabel", {})
    txt = (f"\nKonteks: DATA ASLI perusahaan, diunggah {st.get('loaded_at', '?')[:10]}. "
           f"{rows.get('dim_store', '?')} toko, {rows.get('dim_product', '?')} SKU, "
           f"periode {per.get('mulai', '?')} s.d. {per.get('akhir', '?')}.")
    if st.get("department_tanpa_data"):
        txt += (" Data untuk department berikut BELUM diunggah, jadi jawab bahwa datanya belum tersedia: "
                + ", ".join(st["department_tanpa_data"]) + ".")
    return txt + DEFINITIONS


STYLE = """
Gaya jawaban:
- Bahasa Indonesia profesional, ringkas, untuk manajemen. Jawaban dibaca di Telegram: tanpa tabel,
  pakai poin pendek, maksimal sekitar 12 baris kecuali diminta detail.
- Setiap temuan menyebut angka spesifik dan pembandingnya (target, tahun lalu, atau rata-rata).
- Format uang: Rp 12,3 jt / Rp 4,5 M (miliar). Persen 1 desimal, koma sebagai desimal.
- Selalu sebut kode: toko (misal BDG03, boleh ditambah nama toko), campaign_id, supplier_id, SKU, kasir.
- Akhiri dengan tindakan konkret (apa, oleh siapa: AK/AM/tim terkait).
- Hanya pakai angka dari tool. Jangan mengarang angka, nama, atau penyebab. Kalau penyebab tidak
  terlihat di data, katakan perlu dicek, jangan menebak.
- Kalau tool mengembalikan error, jelaskan singkat apa yang gagal.
"""

DEPT_RULES = """
Selalu panggil tool sebelum menjawab. Periode default 12 bulan terakhir; kalau user menyebut bulan
atau tahun, isi start_month/end_month (YYYY-MM). Cari pola: toko/AM yang jauh di bawah rata-rata,
perubahan mendadak di bulan tertentu, dan selisih besar dengan tahun lalu. Untuk anomali satu toko,
cek trennya per bulan untuk menemukan kapan mulai terjadi.
"""


def model(name: str) -> Gemini:
    """Model Gemini dengan retry otomatis saat kuota per menit habis (429) atau server ramai (503)."""
    return Gemini(
        model=name,
        retry_options=types.HttpRetryOptions(
            attempts=4, initial_delay=3, max_delay=30, http_status_codes=[429, 500, 503]
        ),
    )


def _dept(name: str, title: str, focus: str, tools: list, model_name: str) -> LlmAgent:
    return LlmAgent(
        name=name,
        model=model(model_name),
        description=f"Department {title}: {focus}",
        instruction=f"Kamu analis department {title} Retail HQ. Fokus: {focus}.\n{context()}\n{DEPT_RULES}\n{STYLE}",
        tools=tools,
    )


# (nama tool, nama department, fokus, modul tool)
DEPARTMENTS = [
    ("operation", "Operation",
     "penjualan toko, SPD, STD, AMB, achievement vs target, kinerja AM/AK, display compliance", operation),
    ("merchandise", "Merchandise",
     "kinerja dan margin per kategori, tren kategori, kepatuhan planogram (facing, price tag, shelf talker)", merchandise),
    ("finance", "Finance & Accounting",
     "gross margin, opex vs budget, EBITDA per toko, rasio sewa dan gaji terhadap sales", finance),
    ("supply_chain", "Supply Chain",
     "OOS, SOH 0, fill rate dan ketepatan supplier, SKU yang sering habis", supply_chain),
    ("dc", "Distribution Center",
     "pengiriman DC Denpasar ke toko: fill rate, ketepatan waktu, biaya kirim per unit", dc),
    ("hr", "Human Resources",
     "headcount, turnover karyawan, lembur, produktivitas (sales per jam kerja), biaya gaji", hr),
    ("loss_prevention", "Loss Prevention",
     "shrinkage stock opname, write-off barang hilang/expired, selisih kas, void dan refund kasir", loss_prevention),
    ("it", "IT",
     "tiket gangguan IT, downtime POS, waktu penyelesaian, umur aset POS/printer/CCTV", it),
    ("marketing", "Marketing & CRM",
     "ROI dan uplift campaign promo, member aktif, retensi member per tipe (lokal/turis/ekspat)", marketing),
    ("esg", "ESG",
     "efisiensi chiller per unit, listrik per m2 dan AC, biaya energi, sampah dan daur ulang, kantong plastik", esg),
    ("legal", "Legal",
     "kontrak sewa, izin, dan vendor yang akan/sudah berakhir, nilai perpanjangan", legal),
    ("store_dev", "Store Development",
     "proyek capex dan toko baru: kinerja sejak buka, EBITDA, payback", store_dev),
]


def build_root(model_name: str | None = None) -> LlmAgent:
    model_name = model_name or settings()["GEMINI_MODEL"]
    depts = [_dept(name, title, focus, mod.TOOLS, model_name) for name, title, focus, mod in DEPARTMENTS]
    roster = "\n".join(f"  - {name}: {focus}" for name, _, focus, _ in DEPARTMENTS)
    return LlmAgent(
        name="gm",
        model=model(model_name),
        description="General Manager Retail HQ, koordinator semua department.",
        instruction=f"""Kamu General Manager (GM) Retail HQ yang menjawab pertanyaan manajemen lewat Telegram.
{context()}
Cara kerja:
- Department yang tersedia (masing-masing dipanggil sebagai tool):
{roster}
- Panggil HANYA department yang relevan (biasanya 1-2). Untuk pertanyaan umum ("apa masalah terbesar",
  "ringkas kinerja") panggil paling banyak 4: operation, finance, supply_chain, lalu satu yang paling relevan.
  Kuota model gratis terbatas, jadi hindari memanggil semua department.
- Teruskan pertanyaan ke agent department dengan jelas, termasuk periode, kabupaten, AM, atau toko yang disebut.
- Gabungkan jawaban: prioritaskan 3 masalah dengan dampak terbesar, hubungkan sebab-akibat antar
  department kalau datanya mendukung (misal supplier bermasalah -> OOS -> sales kategori turun).
- Pertanyaan yang tidak bisa dijawab data mana pun (misal harga kompetitor, cuaca, data pribadi karyawan):
  JANGAN panggil department. Jawab singkat 1-2 kalimat bahwa datanya tidak tersedia.
- Untuk pertanyaan periode data atau "data apa yang dipakai", panggil periode_data.
- Kalau hasil tool kosong/nol semua untuk satu department, katakan datanya belum tersedia, jangan menyimpulkan nol.
{STYLE}""",
        tools=[AgentTool(agent=d) for d in depts] + [periode_data],
    )
