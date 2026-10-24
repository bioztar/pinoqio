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
