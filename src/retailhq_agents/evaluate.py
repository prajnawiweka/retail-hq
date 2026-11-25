"""Uji agent dengan pertanyaan yang jawabannya sudah diketahui (pola tertanam di data dummy).

Pakai:  uv run rhq-eval            (semua kasus)
        uv run rhq-eval 1 3        (kasus tertentu)

Hasil lengkap (pertanyaan, jawaban, cek) ditulis ke eval_results.md.
Setiap kasus lulus kalau jawaban memuat SEMUA grup kata kunci (cukup salah satu kata per grup).
Pertanyaan sengaja tidak menyebut jawabannya; kode toko hanya disebut kalau memang pertanyaannya tentang toko itu.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import sys
import time
from pathlib import Path

from retailhq_agents.config import ROOT

CASES = [
    {
        "nama": "Finance: EBITDA negatif",
        "tanya": "Toko mana saja yang EBITDA-nya negatif hampir setiap bulan dalam 12 bulan terakhir, dan apa penyebab utama masing-masing?",
        "harus": [["BDG03"], ["sewa", "rent"]],
    },
    {
        "nama": "Supply Chain: supplier bermasalah",
        "tanya": "Periode Agustus sampai Desember 2025: supplier mana yang fill rate-nya bermasalah, dan apa dampaknya ke stok toko?",
        "harus": [["SUP001"], ["OOS", "out of stock", "habis"]],
    },
    {
        "nama": "Operation: penurunan DPS02",
        "tanya": "Penjualan toko DPS02 kelihatan turun. Sejak bulan apa penurunannya mulai, dan seberapa besar?",
        "harus": [["DPS02"], ["Februari 2026", "Feb 2026", "2026-02", "Februari"]],
    },
    {
        "nama": "Operation: kepatuhan display per AM",
        "tanya": "AM mana yang kepatuhan display atau planogram tokonya paling rendah?",
        "harus": [["Wayan Darmawan"], ["71", "72"]],
    },
    {
        "nama": "Operation: toko baru lemah",
        "tanya": "Toko mana yang achievement-nya paling rendah dalam 12 bulan terakhir?",
        "harus": [["BLL05"]],
    },
    {
        "nama": "Di luar cakupan: legal",
        "tanya": "Kontrak sewa toko mana saja yang akan habis dalam 6 bulan ke depan?",
        "harus": [["belum tersedia", "belum ada", "tidak tersedia", "belum punya", "di luar"]],
    },
]

PAUSE = 15  # detik antar kasus, supaya tidak menabrak batas per menit kuota gratis


def check(answer: str, groups: list[list[str]]) -> list[tuple[list[str], bool]]:
    a = answer.lower()
    return [(g, any(k.lower() in a for k in g)) for g in groups]


async def run(selected: list[int]) -> int:
    from retailhq_agents.runner import Assistant

    bot = Assistant()
    lines = [f"# Hasil uji agent — {dt.datetime.now():%Y-%m-%d %H:%M}", ""]
    passed = 0
    for n, case in enumerate(CASES, 1):
        if selected and n not in selected:
            continue
        print(f"[{n}] {case['nama']} ...", flush=True)
        t0 = time.time()
        await bot.reset(f"eval{n}")
        answer = await bot.ask(f"eval{n}", case["tanya"])
        res = check(answer, case["harus"])
        ok = all(hit for _, hit in res)
        passed += ok
        missing = ["/".join(g) for g, hit in res if not hit]
        print(f"    {'LULUS' if ok else 'GAGAL'} ({time.time() - t0:.0f} dtk)" + (f" — tidak ditemukan: {', '.join(missing)}" if missing else ""))
        lines += [
            f"## {n}. {case['nama']} — {'LULUS' if ok else 'GAGAL'}",
            f"**Pertanyaan:** {case['tanya']}",
            "",
            "**Jawaban:**",
            "",
            answer,
            "",
            "**Cek:** " + "; ".join(f"{'✓' if hit else '✗'} {'/'.join(g)}" for g, hit in res),
            "",
        ]
        if n != (selected or list(range(1, len(CASES) + 1)))[-1]:
            await asyncio.sleep(PAUSE)
    total = len(selected) if selected else len(CASES)
    lines.insert(1, f"\n**{passed}/{total} lulus**\n")
    out = ROOT / "eval_results.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{passed}/{total} lulus. Detail jawaban: {out.name}")
    return 0 if passed == total else 1


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    selected = [int(a) for a in sys.argv[1:] if a.isdigit()]
    sys.exit(asyncio.run(run(selected)))


if __name__ == "__main__":
    main()
