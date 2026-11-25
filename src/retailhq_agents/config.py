"""Baca .env sekali dan siapkan variabel yang dipakai google-genai / ADK."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "gemini-3.5-flash"
FALLBACK_MODEL = "gemini-flash-lite-latest"


def _read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.split("#", 1)[0].strip().strip('"').strip("'")
    keys = set(env) | {"GCP_PROJECT_ID", "BQ_LOCATION", "BQ_DATASET_MART", "BQ_DATASET_STAGING", "GEMINI_API_KEY", "GEMINI_MODEL",
                       "GEMINI_FALLBACK_MODEL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USER_IDS"}
    for k in keys:
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


@lru_cache
def settings() -> dict[str, str]:
    env = _read_env(ROOT / ".env")
    if not env.get("GCP_PROJECT_ID"):
        raise SystemExit("GCP_PROJECT_ID belum diisi di .env")
    if not env.get("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY belum diisi di .env (buat gratis di https://aistudio.google.com/apikey)")
    # google-genai membaca GOOGLE_API_KEY; pakai Gemini API (AI Studio), bukan Vertex AI.
    os.environ["GOOGLE_API_KEY"] = env["GEMINI_API_KEY"]
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
    env.setdefault("BQ_DATASET_MART", "mart")
    env["GEMINI_MODEL"] = env.get("GEMINI_MODEL") or DEFAULT_MODEL
    env["GEMINI_FALLBACK_MODEL"] = env.get("GEMINI_FALLBACK_MODEL") or FALLBACK_MODEL
    return env
