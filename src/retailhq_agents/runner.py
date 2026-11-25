"""Menjalankan agent GM: satu sesi percakapan per user/chat.

Kalau model utama tetap sibuk (503) atau kuotanya habis (429) setelah retry otomatis,
pertanyaan diulang sekali dengan model cadangan (GEMINI_FALLBACK_MODEL).
"""
from __future__ import annotations

import asyncio
import logging

from google.adk.runners import InMemoryRunner
from google.genai import types

from retailhq_agents.agents import build_root
from retailhq_agents.config import settings

APP = "retail_hq"
log = logging.getLogger(__name__)

# ADK mencetak traceback panjang untuk setiap error model; jawaban ramah sudah kita tangani sendiri.
logging.getLogger("google_adk").setLevel(logging.CRITICAL)


def _overloaded(e: Exception) -> bool:
    s = str(e)
    return any(k in s for k in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "overloaded"))


class Assistant:
    def __init__(self) -> None:
        s = settings()
        self.models = [s["GEMINI_MODEL"]]
        if s["GEMINI_FALLBACK_MODEL"] not in self.models:
            self.models.append(s["GEMINI_FALLBACK_MODEL"])
        self.runners: dict[str, InMemoryRunner] = {}
        self.sessions: dict[tuple[str, str], str] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _runner(self, model_name: str) -> InMemoryRunner:
        if model_name not in self.runners:
            self.runners[model_name] = InMemoryRunner(agent=build_root(model_name), app_name=APP)
        return self.runners[model_name]

    async def reset(self, user_id: str) -> None:
        for key in [k for k in self.sessions if k[1] == user_id]:
            self.sessions.pop(key)

    async def _session(self, model_name: str, user_id: str) -> str:
        key = (model_name, user_id)
        if key not in self.sessions:
            s = await self._runner(model_name).session_service.create_session(app_name=APP, user_id=user_id)
            self.sessions[key] = s.id
        return self.sessions[key]

    async def _run(self, model_name: str, user_id: str, text: str) -> str:
        runner = self._runner(model_name)
        session_id = await self._session(model_name, user_id)
        msg = types.Content(role="user", parts=[types.Part(text=text)])
        answer, used = "", []
        async for ev in runner.run_async(user_id=user_id, session_id=session_id, new_message=msg):
            for call in ev.get_function_calls() or []:
                used.append(call.name)
                log.info("tool: %s %s", call.name, dict(call.args or {}))
            if ev.is_final_response() and ev.content and ev.content.parts:
                answer = "".join(p.text or "" for p in ev.content.parts if not getattr(p, "thought", False))
        log.info("model %s, tool dipanggil: %s", model_name, ", ".join(used) or "-")
        return answer.strip()

    async def ask(self, user_id: str, text: str) -> str:
        lock = self._locks.setdefault(user_id, asyncio.Lock())
        async with lock:  # satu pertanyaan per user sekaligus
            last: Exception | None = None
            for i, model_name in enumerate(self.models):
                try:
                    answer = await self._run(model_name, user_id, text)
                    if i > 0:
                        answer += f"\n\n(dijawab model cadangan {model_name} karena model utama sedang sibuk)"
                    return answer or "Maaf, belum ada jawaban. Coba ulangi dengan pertanyaan yang lebih spesifik."
                except Exception as e:  # noqa: BLE001
                    last = e
                    if not _overloaded(e):
                        break
                    log.warning("model %s sibuk/kuota habis, coba model berikutnya", model_name)
            return friendly_error(last)


def friendly_error(e: Exception | None) -> str:
    s = str(e)
    if "503" in s or "UNAVAILABLE" in s:
        return "Server Gemini sedang ramai (503). Ini sementara; coba lagi 1–2 menit lagi."
    if "429" in s or "RESOURCE_EXHAUSTED" in s:
        return "Kuota gratis Gemini sedang habis (batas per menit/hari). Tunggu sekitar 1 menit lalu coba lagi."
    if "API key" in s or "API_KEY" in s or "PERMISSION_DENIED" in s or "403" in s:
        return "Akses ditolak. Cek GEMINI_API_KEY di .env dan login gcloud untuk BigQuery."
    if "404" in s and "model" in s.lower():
        return "Model Gemini tidak ditemukan. Isi GEMINI_MODEL di .env dengan model yang tersedia di AI Studio."
    log.error("agent error: %s", s[:500])
    return f"Terjadi error: {type(e).__name__}: {s[:200]}"
