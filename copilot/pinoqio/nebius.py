"""Nebius Token Factory client (OpenAI-compatible chat completions): JSON mode, temperature 0.

Second model with its own jobs: fallback analyst, contradiction verifier, post-call summary.
Default calls walk a model chain: on 429/5xx/timeout the next model is tried at once, no sleeping.
"""
import asyncio
import logging

import httpx

from pinoqio import config
from pinoqio.gemma import parse_json

log = logging.getLogger(__name__)

TIMEOUT_S = 8.0
RETRY_CODES = frozenset({403, 429})
ROUND_PAUSE_S = 0.6
FALLBACK_MODEL ="Qwen/Qwen3-30B-A3B-Instruct-2507"


class NebiusError(RuntimeError):
    """Nebius call failed or returned unusable output."""


class _Retryable(Exception):
    """429/5xx/timeout/transport error: worth trying another model."""


def short_name(model: str) -> str:
    """'deepseek-ai/DeepSeek-V4.1-Flash' -> 'DeepSeek'; 'Qwen/Qwen3-235B-...' -> 'Qwen3'; for badges."""
    return model.split("/")[-1].split("-")[0]


def chain() -> tuple[str, ...]:
    """Configured model first, then the fallback (de-duplicated)."""
    primary = config.nebius_model()
    return (primary,) if primary == FALLBACK_MODEL else (primary, FALLBACK_MODEL)


async def _post(prompt: str, system: str | None, model: str, timeout: float) -> str:
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
        raise _Retryable(f"http {r.status_code} {short_name(model)}: {r.text[:120]!r}")
    if r.status_code >= 400:
        raise NebiusError(f"nebius http {r.status_code}")
    try:
        return r.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, ValueError) as e:
        raise NebiusError("unexpected nebius response shape") from e


async def _once(prompt: str, system: str | None, model: str, timeout: float) -> dict:
    """One attempt on one model. _Retryable for transient trouble, NebiusError otherwise."""
    try:
        return parse_json(await _post(prompt, system, model, timeout))
    except _Retryable:
        raise
    except httpx.TransportError as e:  # TimeoutException is a TransportError
        raise _Retryable(f"{type(e).__name__} {short_name(model)}") from e
    except RuntimeError as e:  # NebiusError, GemmaError (bad JSON), missing key
        raise NebiusError(str(e)) from e


async def ask_json_model(
    prompt: str, system: str | None = None, model: str | None = None, timeout: float = TIMEOUT_S
) -> tuple[dict, str]:
    """(JSON object, model that answered). Explicit `model`: that model only, one retry.
    No model: the chain, next model immediately on transient failure. Raises NebiusError."""
    if model:
        for attempt in (0, 1):
            try:
                return await _once(prompt, system, model, timeout), model
            except _Retryable as e:
                if attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
                raise NebiusError(f"nebius failed twice ({e})") from e
    failures = []
    # The gateway returns bursts of HTML 503s for every model at once (seen live, gone seconds
    # later), so after a full pass fails, pause briefly and walk the chain once more.
    for round_ in (0, 1):
        if round_:
            await asyncio.sleep(ROUND_PAUSE_S)
        for m in chain():
            try:
                return await _once(prompt, system, m, timeout), m
            except _Retryable as e:
                log.warning("nebius %s", e)
                failures.append(str(e))
    raise NebiusError("nebius chain failed: " + "; ".join(failures))


async def ask_json(
    prompt: str, system: str | None = None, model: str | None = None, timeout: float = TIMEOUT_S
) -> dict:
    return (await ask_json_model(prompt, system, model, timeout))[0]
