"""Utterance stream -> utterances plus a Verdict after each counterparty utterance."""
import logging
from dataclasses import replace
from typing import AsyncIterator

from pinoqio.analyst import Analysis, Ask, analyze, merge_ledger
from pinoqio.events import Utterance, Verdict
from pinoqio.gemma import ask_json
from pinoqio.score import score

log = logging.getLogger(__name__)


async def verdicts(
    utterances: AsyncIterator[Utterance], ask: Ask = ask_json
) -> AsyncIterator[Utterance | Verdict]:
    history: tuple[Utterance, ...] = ()
    ledger = ()
    async for u in utterances:
        history = history + (u,)
        yield u
        if u.speaker != "them":
            continue
        try:
            analysis = await analyze(history, ledger, ask)
        except Exception as e:  # a failed call must never kill the live pipeline
            log.warning("analyst failed for utterance %s: %s", u.id, type(e).__name__)
            analysis = Analysis(utterance_id=u.id)  # vocal-only verdict
        ledger = merge_ledger(ledger, analysis.ledger_updates)
        yield replace(score(analysis, u.prosody), ledger=ledger)
