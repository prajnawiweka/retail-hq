"""Definisi agent: GM (koordinator) + department Operation, Finance, Supply Chain.

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
from retailhq_agents.tools import finance, operation, supply_chain
from retailhq_agents.tools.common import periode_data

CONTEXT = """
Konteks perusahaan: Retail HQ, jaringan 50 minimarket fiktif di Bali (8 kabupaten), 300 SKU,
25 supplier, 1 DC di Denpasar. Data simulasi Nov 2024 s.d. Okt 2026. Struktur: Area Manager (AM)
membawahi beberapa toko, Area Koordinator (AK) membawahi beberapa AM.
Definisi: SPD = net sales per hari buka per toko; STD = jumlah struk; AMB = net sales / STD;
achievement = net sales / target; EBITDA = gross profit - opex; OOS = SKU ditandai habis di toko;
SOH 0 = stok sistem nol (tidak selalu sama dengan OOS).
"""

STYLE = """
Gaya jawaban:
- Bahasa Indonesia profesional, ringkas, untuk manajemen. Jawaban dibaca di Telegram: tanpa tabel,
  pakai poin pendek, maksimal sekitar 12 baris kecuali diminta detail.
- Setiap temuan menyebut angka spesifik dan pembandingnya (target, tahun lalu, atau rata-rata).
- Format uang: Rp 12,3 jt / Rp 4,5 M (miliar). Persen 1 desimal, koma sebagai desimal.
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
        instruction=f"Kamu analis department {title} Retail HQ. Fokus: {focus}.\n{CONTEXT}\n{DEPT_RULES}\n{STYLE}",
        tools=tools,
    )


def build_root(model_name: str | None = None) -> LlmAgent:
    model_name = model_name or settings()["GEMINI_MODEL"]
    ops = _dept(
        "operation",
        "Operation",
        "penjualan toko, SPD, STD, AMB, achievement vs target, kinerja AM/AK, display compliance",
        operation.TOOLS,
        model_name,
    )
    fin = _dept(
        "finance",
        "Finance & Accounting",
        "gross margin, opex vs budget, EBITDA per toko, rasio sewa dan gaji terhadap sales",
        finance.TOOLS,
        model_name,
    )
    sc = _dept(
        "supply_chain",
        "Supply Chain & DC",
        "OOS, SOH 0, fill rate dan ketepatan supplier, SKU yang sering habis, pengiriman DC ke toko",
        supply_chain.TOOLS,
        model_name,
    )
    return LlmAgent(
        name="gm",
        model=model(model_name),
        description="General Manager Retail HQ, koordinator semua department.",
        instruction=f"""Kamu General Manager (GM) Retail HQ yang menjawab pertanyaan manajemen lewat Telegram.
{CONTEXT}
Cara kerja:
- Tentukan department yang relevan, lalu panggil HANYA agent itu (operation, finance, supply_chain).
  Pertanyaan umum ("bagaimana kinerja bulan ini", "apa masalah terbesar") boleh memanggil ketiganya.
- Teruskan pertanyaan ke agent department dengan jelas, termasuk periode, kabupaten, AM, atau toko yang disebut.
- Gabungkan jawaban: prioritaskan 3 masalah dengan dampak terbesar, hubungkan sebab-akibat antar
  department kalau datanya mendukung (misal supplier bermasalah -> OOS -> sales kategori turun).
- Pertanyaan di luar cakupan (HR, legal/kontrak, IT, marketing/campaign, ESG, loss prevention, store
  development belum punya agent): JANGAN panggil agent lain. Jawab singkat 1-2 kalimat bahwa department
  itu belum tersedia di versi ini, lalu sebut pertanyaan apa yang bisa dijawab.
- Untuk pertanyaan periode data, panggil periode_data.
{STYLE}""",
        tools=[AgentTool(agent=ops), AgentTool(agent=fin), AgentTool(agent=sc), periode_data],
    )
