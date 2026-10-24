"""Async Gemma client: temperature 0, JSON out, 10 s timeout, one retry on 429/5xx/403.

Pattern from the judge lane (403 shows up intermittently under load on the free tier).
"""
import asyncio
import json
import re

from google import genai
from google.genai import errors, types

from pinoqio import config

MODEL = "gemma-4-26b-a4b-it"  # 31b timed out at 40 s, do not use
TIMEOUT_S = 10.0
RETRY_CODES = frozenset({403, 429})

_client: genai.Client | None = None


class GemmaError(RuntimeError):
    """Gemma call failed or returned unusable output."""


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=config.gemini_key())
    return _client


def parse_json(text: str) -> dict:
    """Parse a JSON object, tolerating ```json fences and prose around it."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise GemmaError("no JSON object in response") from None
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as e:
            raise GemmaError(f"bad JSON: {e}") from e
    if not isinstance(data, dict):
        raise GemmaError("JSON is not an object")
    return data


def _retryable(e: errors.APIError) -> bool:
    code = getattr(e, "code", None) or 0
    return code in RETRY_CODES or code >= 500


async def _call(prompt: str, system: str | None) -> str:
    resp = await asyncio.wait_for(
        _get_client().aio.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                system_instruction=system,
                response_mime_type="application/json",
                # default thinking burns ~500 tokens (15 s); MINIMAL is the only level this model accepts
                thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
            ),
        ),
        TIMEOUT_S,
    )
    return resp.text or ""


async def ask_json(prompt: str, system: str | None = None) -> dict:
    """One deterministic call returning a JSON object. Raises GemmaError on any failure."""
    for attempt in (0, 1):
        try:
            return parse_json(await _call(prompt, system))
        except errors.APIError as e:
            if attempt == 0 and _retryable(e):
                await asyncio.sleep(1.0)
                continue
            raise GemmaError(f"gemma api error {getattr(e, 'code', '?')}") from e
        except asyncio.TimeoutError as e:
            raise GemmaError("gemma timeout") from e
    raise GemmaError("unreachable")
