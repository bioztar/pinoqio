"""Lazy env loading. Keys live only in a gitignored .env; values are never printed or logged."""
import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load() -> None:
    load_dotenv(os.environ.get("PINOQIO_ENV_FILE", _REPO_ROOT / ".env"))


def _require(name: str) -> str:
    _load()
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing setting {name} (set it in .env or PINOQIO_ENV_FILE)")
    return value


def gemini_key() -> str:
    return _require("GEMINI_API_KEY")


def elevenlabs_key() -> str:
    return _require("ELEVENLABS_API_KEY")


def nebius_key() -> str:
    return _require("NEBIUS_API_KEY")


def _optional(name: str, default: str) -> str:
    _load()
    return os.environ.get(name) or default


def nebius_base_url() -> str:
    return _optional("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1/")


def nebius_model() -> str:
    return _optional("NEBIUS_MODEL", "deepseek-ai/DeepSeek-V4.1-Flash")  # fastest + correct on bench, scripts/nebius_bench.py
