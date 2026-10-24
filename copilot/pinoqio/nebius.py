"""Nebius Token Factory client (OpenAI-compatible chat completions): JSON mode, temperature 0.

Second model with its own jobs: fallback analyst, contradiction verifier, post-call summary.
"""
import asyncio

import httpx

from pinoqio import config
from pinoqio.gemma import parse_json

TIMEOUT_S = 8.0
RETRY_CODES = frozenset({403, 429})


class NebiusError(RuntimeError):
    """Nebius call failed or returned unusable output."""


def short_name(model: str) -> str:
    """'deepseek-ai/DeepSeek-V4.1-Flash' -> 'DeepSeek'; 'Qwen/Qwen3-235B-...' -> 'Qwen3'; for badges."""
    return model.split("/")[-1].split("-")[0]


async def _post(prompt: str, system: str | None, model: str, timeout: float = TIMEOUT_S) -> str:
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            config.nebius_base_url().rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {config.nebius_key()}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
        )
    if r.status_code in RETRY_CODES or r.status_code >= 500:
        raise _Retryable(r.status_code)
    if r.status_code >= 400:
        raise NebiusError(f"nebius http {r.status_code}")
    try:
        return r.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, ValueError) as e:
        raise NebiusError("unexpected nebius response shape") from e


class _Retryable(Exception):
    pass


async def ask_json(
    prompt: str, system: str | None = None, model: str | None = None, timeout: float = TIMEOUT_S
) -> dict:
    """One deterministic call returning a JSON object. Retries once. Raises NebiusError."""
    model = model or config.nebius_model()
    for attempt in (0, 1):
        try:
            return parse_json(await _post(prompt, system, model, timeout))
        except (_Retryable, httpx.TransportError) as e:  # TimeoutException is a TransportError
            if attempt == 0:
                await asyncio.sleep(0.5)
                continue
            raise NebiusError(f"nebius failed twice ({type(e).__name__})") from e
        except RuntimeError as e:  # NebiusError, GemmaError (bad JSON), missing key
            raise NebiusError(str(e)) from e
    raise NebiusError("unreachable")
