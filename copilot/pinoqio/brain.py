"""Utterance stream -> utterances plus a Verdict after each counterparty utterance.

Gemma 4 analyses every utterance; Nebius is the fallback analyst (Gemma error or > 8 s) and the
verifier of any contradiction / number drift Gemma reports (see verifier.py).
"""
import asyncio
import logging
from dataclasses import replace
from typing import AsyncIterator, Sequence

from pinoqio import nebius
from pinoqio.analyst import Analysis, Ask, analyze, merge_ledger
from pinoqio.events import Chip, LedgerItem, Utterance, Verdict
from pinoqio.gemma import ask_json
from pinoqio.score import score
from pinoqio.verifier import Verification, refine

log = logging.getLogger(__name__)

HEDGE_S = 3.5          # Gemma alone for this long, then Nebius races it
TOTAL_BUDGET_S = 11.0  # analysis deadline per line; 1 s over Gemma's own 10 s timeout so a slow Gemma still lands when Nebius is down
GEMMA_LABEL = "Gemma 4"
FALLBACK_LABEL = "Nebius (fallback)"
NEBIUS_ANALYST_TIMEOUT_S = 4.5  # per model in the Nebius chain


async def _nebius_analyst(prompt: str, system: str | None) -> dict:
    return await nebius.ask_json(prompt, system, timeout=NEBIUS_ANALYST_TIMEOUT_S)


def _model_chip(label: str) -> Chip:
    # kind "model" is not in events.ChipKind (frozen); the UI shows these in the badge, not as evidence
    return Chip("model", label, 0.0)  # type: ignore[arg-type]


async def _analyze(
    history: Sequence[Utterance], ledger: Sequence[LedgerItem], ask: Ask, fallback: Ask
) -> tuple[Analysis, str | None]:
    """(analysis, label of the model that answered). Never raises; (neutral, None) if both fail."""
    uid = history[-1].id
    gemma = asyncio.create_task(analyze(history, ledger, ask))
    # Gemma gets HEDGE_S alone. If it has not answered validly by then (slow or failed), Nebius starts
    # in parallel and the first valid answer wins; Gemma wins ties.
    await asyncio.wait({gemma}, timeout=HEDGE_S)
    if gemma.done() and not gemma.exception():
        return gemma.result(), GEMMA_LABEL
    if gemma.done():
        log.warning("gemma failed for utterance %s: %s: %s", uid, type(gemma.exception()).__name__, gemma.exception())
    backup = asyncio.create_task(analyze(history, ledger, fallback))
    racers = {gemma: GEMMA_LABEL, backup: FALLBACK_LABEL}
    deadline = asyncio.get_running_loop().time() + TOTAL_BUDGET_S - HEDGE_S
    try:
        while racers:
            left = deadline - asyncio.get_running_loop().time()
            done, _ = await asyncio.wait(racers, timeout=max(left, 0), return_when=asyncio.FIRST_COMPLETED)
            if not done:
                log.warning("no analyst answered utterance %s within %.0f s", uid, TOTAL_BUDGET_S)
                break
            for task in sorted(done, key=lambda t: t is not gemma):  # Gemma first on ties
                if task.cancelled() or task.exception():
                    log.warning("%s failed for utterance %s: %s", racers[task], uid, task.exception() if not task.cancelled() else "cancelled")
                    del racers[task]
                else:
                    return task.result(), racers[task]
    finally:
        for task in racers:
            task.cancel()  # a failed call must never kill the live pipeline; stragglers are dropped
    return Analysis(utterance_id=uid), None  # vocal-only verdict


def _badge(answered: str | None, v: Verification | None) -> tuple[Chip, ...]:
    chips = [_model_chip(answered)] if answered else []
    if v:
        verb = "verified" if v.is_contradiction else "checked"
        chips.append(_model_chip(f"{verb} by {nebius.short_name(v.model)}"))
    return tuple(chips)


async def verdicts(
    utterances: AsyncIterator[Utterance],
    ask: Ask = ask_json,
    fallback: Ask = _nebius_analyst,
    verify_ask: Ask | None = None,
) -> AsyncIterator[Utterance | Verdict]:
    history: tuple[Utterance, ...] = ()
    ledger: tuple[LedgerItem, ...] = ()
    async for u in utterances:
        history = history + (u,)
        yield u
        if u.speaker != "them":
            continue
        analysis, answered = await _analyze(history, ledger, ask, fallback)
        analysis, verification = await refine(analysis, history, ledger, verify_ask)
        ledger = merge_ledger(ledger, analysis.ledger_updates)
        v = score(analysis, u.prosody)
        yield replace(v, chips=v.chips + _badge(answered, verification), ledger=ledger)
