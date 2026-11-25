"""Bot Telegram untuk agent Retail HQ (mode polling, jalan di laptop; tidak perlu server).

Pakai:  uv run rhq-bot

Opsional di .env:
  TELEGRAM_ALLOWED_USER_IDS=12345678,87654321   hanya user ini yang boleh bertanya.
  Kosong = semua orang yang tahu username bot bisa bertanya (memakai kuota Gemini kamu).
  Kirim /id ke bot untuk melihat user id kamu.
"""
from __future__ import annotations

import html
import logging
import re

from retailhq_agents.config import settings

log = logging.getLogger("retailhq_agents.telegram")
LIMIT = 4000  # batas Telegram 4096 karakter per pesan

WELCOME = (
    "Halo, saya GM Retail HQ. Saya koordinasi 12 department: Operation, Merchandise, Finance, Supply Chain, "
    "DC, HR, Loss Prevention, IT, Marketing, ESG, Legal, dan Store Development untuk 50 toko di Bali "
    "(data simulasi Nov 2024 – Okt 2026).\n\n"
    "Contoh:\n"
    "• Apa 3 masalah terbesar 12 bulan terakhir?\n"
    "• Toko mana yang EBITDA-nya negatif dan kenapa?\n"
    "• Kasir mana yang transaksinya janggal?\n"
    "• Kontrak sewa mana yang habis dalam 6 bulan?\n"
    "• Toko mana yang paling boros listrik?\n\n"
    "/selesai untuk mengakhiri percakapan, /reset untuk mulai topik baru."
)


def to_html(md: str) -> str:
    """Markdown sederhana dari Gemini -> HTML Telegram (bold, judul, bullet)."""
    s = html.escape(md)
    s = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", s, flags=re.M)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
    s = re.sub(r"^\s*[*-]\s+", "• ", s, flags=re.M)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def chunks(text: str, size: int = LIMIT) -> list[str]:
    out, buf = [], ""
    for para in text.split("\n"):
        if len(buf) + len(para) + 1 > size and buf:
            out.append(buf)
            buf = ""
        buf += para + "\n"
    if buf.strip():
        out.append(buf)
    return out or [text[:size]]


def main() -> None:
    from telegram import BotCommand, Update
    from telegram.constants import ChatAction, ParseMode
    from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

    from retailhq_agents.runner import Assistant

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    s = settings()
    token = s.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN belum diisi di .env (buat lewat @BotFather di Telegram)")
    allowed = {x.strip() for x in s.get("TELEGRAM_ALLOWED_USER_IDS", "").split(",") if x.strip()}
    if not allowed:
        log.warning("TELEGRAM_ALLOWED_USER_IDS kosong: semua user Telegram bisa bertanya ke bot ini.")

    assistant = Assistant()

    def permitted(update: Update) -> bool:
        return not allowed or str(update.effective_user.id) in allowed

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(WELCOME)

    async def whoami(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(f"User id kamu: {update.effective_user.id}")

    async def reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await assistant.reset(str(update.effective_chat.id))
        await update.message.reply_text("Percakapan dimulai ulang.")

    async def end(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await assistant.reset(str(update.effective_chat.id))
        await update.message.reply_text(
            "Percakapan selesai dan riwayatnya dihapus. Kirim pertanyaan kapan saja untuk mulai lagi."
        )

    async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        from retailhq_agents.bq import data_state

        st = data_state()
        per = st.get("periode", {})
        lines = [f"Mode data: {'DATA ASLI' if st.get('mode') == 'asli' else 'data dummy (simulasi)'}"]
        if per:
            lines.append(f"Periode: {per.get('mulai')} s.d. {per.get('akhir')}")
        if st.get("loaded_at"):
            lines.append(f"Dimuat: {st['loaded_at'].replace('T', ' ')[:16]}")
        if st.get("department_tanpa_data"):
            lines.append("Belum ada data: " + ", ".join(st["department_tanpa_data"]))
        await update.message.reply_text("\n".join(lines))

    async def set_menu(app) -> None:
        await app.bot.set_my_commands([
            BotCommand("start", "Mulai dan lihat contoh pertanyaan"),
            BotCommand("selesai", "Akhiri percakapan"),
            BotCommand("reset", "Mulai topik baru"),
            BotCommand("status", "Data yang sedang dipakai"),
            BotCommand("id", "Lihat user id Telegram kamu"),
        ])

    async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not permitted(update):
            await update.message.reply_text("Maaf, bot ini privat.")
            return
        chat = update.effective_chat
        await ctx.bot.send_chat_action(chat.id, ChatAction.TYPING)
        log.info("pertanyaan dari %s: %s", update.effective_user.id, update.message.text)
        answer = await assistant.ask(str(chat.id), update.message.text)
        for part in chunks(answer):
            try:
                await update.message.reply_text(to_html(part), parse_mode=ParseMode.HTML)
            except Exception:  # noqa: BLE001 - HTML tidak valid: kirim teks polos
                await update.message.reply_text(part)

    app = Application.builder().token(token).concurrent_updates(True).post_init(set_menu).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("id", whoami))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler(["selesai", "end"], end))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("Bot jalan dengan model %s. Tekan Ctrl+C untuk berhenti.", s["GEMINI_MODEL"])
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
