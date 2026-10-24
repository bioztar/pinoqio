"""Utterance stream -> utterances plus a Verdict after each counterparty utterance.

Gemma 4 analyses every utterance; Nebius is the fallback analyst (Gemma error or > 8 s) and the
verifier of any contradiction / number drift Gemma reports (see verifier.py).
"""
import asyncio
import logging
from dataclasses import replace
from typing import AsyncIterator, Sequence

from pinoqio import config, nebius
from pinoqio.analyst import Analysis, Ask, analyze, merge_ledger
from pinoqio.events import Chip, LedgerItem, Utterance, Verdict
from pinoqio.gemma import ask_json
from pinoqio.score import score
from pinoqio.verifier import Verification, refine

log = logging.getLogger(__name__)

GEMMA_BUDGET_S = 8.0
GEMMA_LABEL = "Gemma 4"


def _model_chip(label: str) -> Chip:
    # kind "model" is not in events.ChipKind (frozen); the UI shows these in the badge, not as evidence
    return Chip("model", label, 0.0)  # type: ignore[arg-type]


async def _analyze(
    history: Sequence[Utterance], ledger: Sequence[LedgerItem], ask: Ask, fallback: Ask
) -> tuple[Analysis, str | None]:
    """(analysis, label of the model that answered). Never raises; (neutral, None) if both fail."""
    uid = history[-1].id
    try:
        return await asyncio.wait_for(analyze(history, ledger, ask), GEMMA_BUDGET_S), GEMMA_LABEL
    except Exception as e:  # a failed call must never kill the live pipeline
        log.warning("gemma failed for utterance %s: %s, falling back to nebius", uid, type(e).__name__)
    try:
        label = f"{nebius.short_name(config.nebius_model())} (fallback)"
        return await analyze(history, ledger, fallback), label
    except Exception as e:
        log.warning("fallback failed for utterance %s: %s", uid, type(e).__name__)
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
    fallback: Ask = nebius.ask_json,
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
