"""Thin Gemma 4 client for the judge lane. Uses its own key (GEMINI_API_KEY_JUDGE) per AGENTS.md."""
import os
import threading
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

FAST = "gemma-4-26b-a4b-it"
STRONG = "gemma-4-31b-it"

_KEY_VARS = ("GEMINI_API_KEY_JUDGE", "GEMINI_API_KEY", "GOOGLE_API_KEY")
_client = None


def client():
    """Created on first use, so --help and argument errors work without a key.
    Our own key locally; the organizers' run may provide one of the standard names instead."""
    global _client
    if _client is None:
        key = next((os.environ[v] for v in _KEY_VARS if os.environ.get(v)), None)
        if not key:
            raise SystemExit(f"No Gemini API key: set one of {', '.join(_KEY_VARS)}")
        _client = genai.Client(api_key=key)
    return _client


# Gemma 4 free tier allows about 15 requests per minute; spacing request starts avoids 429 backoff storms
_RPM = float(os.environ.get("JUDGE_RPM", "14"))
_lock = threading.Lock()
_next_slot = 0.0


def _wait_for_slot():
    global _next_slot
    with _lock:
        now = time.monotonic()
        start = max(now, _next_slot)
        _next_slot = start + 60.0 / _RPM
    time.sleep(max(0.0, start - now))


def ask(prompt: str, model: str = FAST, system: str | None = None, retries: int = 6) -> dict:
    """One deterministic call. Returns text, token usage and latency for cost/speed accounting.
    Retries on rate limits (429) and transient server errors (5xx) with exponential backoff."""
    for attempt in range(retries):
        _wait_for_slot()
        t0 = time.perf_counter()
        try:
            resp = client().models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0, system_instruction=system),
            )
        except (errors.ServerError, errors.ClientError) as e:
            # 429 is a rate limit; 403 shows up intermittently under parallel load on the free tier
            transient = getattr(e, "code", None) in (403, 429)
            if attempt == retries - 1 or (isinstance(e, errors.ClientError) and not transient):
                raise
            if isinstance(e, errors.ServerError) and model == STRONG:
                model = FAST  # 31B returns 500 for long stretches on the free tier; 26B keeps the run alive
                continue
            time.sleep(min(60, 4 * 2**attempt))
            continue
        usage = resp.usage_metadata
        return {
            "text": resp.text or "",
            "model": model,
            "in_tokens": usage.prompt_token_count if usage else 0,
            "out_tokens": usage.candidates_token_count if usage else 0,
            "seconds": round(time.perf_counter() - t0, 3),
        }
