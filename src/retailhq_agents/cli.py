"""Tanya agent dari Terminal, tanpa Telegram.

Pakai:  uv run rhq-ask "Toko mana yang achievement-nya paling rendah?"
        uv run rhq-ask              (mode percakapan; ketik 'reset' untuk mulai ulang, 'keluar' untuk berhenti)
        uv run rhq-ask --tools      (uji semua tool BigQuery tanpa Gemini)
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys


def _tool_check() -> None:
    from retailhq_agents.agents import DEPARTMENTS
    from retailhq_agents.tools.common import periode_data

    print("periode_data:", periode_data())
    ok = True
    need = {"tren_bulanan_toko": {"store_code": "DPS02"}, "tren_kategori_bulanan": {"category": "Minuman"}}
    seen = set()
    for name, _, _, mod in DEPARTMENTS:
        print(f"[{name}]")
        for fn in mod.TOOLS:
            if fn.__name__ in seen:
                continue
            seen.add(fn.__name__)
            kwargs = need.get(fn.__name__, {})
            out = fn(**kwargs)
            err = out.get("error") if isinstance(out, dict) else None
            ok &= not err
            size = len(json.dumps(out, default=str))
            print(f"  {'GAGAL' if err else 'ok   '} {fn.__name__:<24} {err or f'{size:,} karakter'}")
    sys.exit(0 if ok else 1)


async def _chat(question: str | None) -> None:
    from retailhq_agents.runner import Assistant

    bot = Assistant()
    if question:
        print(await bot.ask("cli", question))
        return
    print("Retail HQ — tanya apa saja soal 12 department. 'keluar' untuk berhenti, 'reset' untuk topik baru.")
    while True:
        try:
            q = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"keluar", "exit", "quit"}:
            break
        if q.lower() == "reset":
            await bot.reset("cli")
            print("Percakapan dimulai ulang.")
            continue
        if q:
            print("\n" + await bot.ask("cli", q))


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = sys.argv[1:]
    if args and args[0] == "--tools":
        _tool_check()
    if args and args[0] in {"-v", "--verbose"}:
        logging.getLogger("retailhq_agents").setLevel(logging.INFO)
        args = args[1:]
    asyncio.run(_chat(" ".join(args) or None))


if __name__ == "__main__":
    main()
