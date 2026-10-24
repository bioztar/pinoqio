"""Second-model check of Gemma's contradiction / number-drift findings (runs on Nebius).

A confirmed drift is upgraded to a Contradiction; a rejected contradiction is dropped. If the
verifier fails, Gemma's result is kept but confidence is capped below the public-interjection bar.
"""
import logging
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

from pinoqio import config, nebius
from pinoqio.analyst import Analysis, Ask, _norm, format_ledger, format_transcript
from pinoqio.events import Contradiction, LedgerItem, Utterance

log = logging.getLogger(__name__)

SYSTEM = (Path(__file__).parent / "prompts" / "verifier.md").read_text()
UNVERIFIED_CAP = 0.8  # below voice.INTERJECT_MIN_CONF (0.85)


@dataclass(frozen=True)
class Claim:
    item: str
    then_quote: str
    then_id: int
    then_t: float
    now_quote: str
    now_t: float


@dataclass(frozen=True)
class Verification:
    is_contradiction: bool
    confidence: float
    reason: str
    model: str


def _clause(text: str, value: str) -> str:
    """The sentence of text that mentions value, else the whole text (always a verbatim substring)."""
    v = _norm(value)
    for s in re.split(r"(?<=[.!?])\s+", text):
        if v and v in _norm(s):
            return s.strip()
    return text.strip()


def claim_from(analysis: Analysis, history: Sequence[Utterance]) -> Claim | None:
    """The statement pair to verify, or None when Gemma flagged nothing. history[-1] is current."""
    now = history[-1]
    by_id = {u.id: u for u in history}
    c, d = analysis.contradiction, analysis.number_drift
    if c and c.then_utterance_id in by_id:
        then = by_id[c.then_utterance_id]
        return Claim(d.item if d else "(not named)", c.then_quote, then.id, then.t_start, c.now_quote, now.t_start)
    if d and d.then_id in by_id:
        then = by_id[d.then_id]
        return Claim(d.item, _clause(then.text, d.then_value), then.id, then.t_start, _clause(now.text, d.now_value), now.t_start)
    return None


def _clock(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


async def verify(
    claim: Claim, history: Sequence[Utterance], ledger: Sequence[LedgerItem], ask: Ask | None = None, model: str | None = None
) -> Verification:
    """Raises on call failure or malformed output."""
    model = model or config.nebius_model()
    prompt = (
        f"ITEM: {claim.item}\n"
        f'EARLIER (utterance {claim.then_id}, {_clock(claim.then_t)}): "{claim.then_quote}"\n'
        f'CURRENT (utterance {history[-1].id}, {_clock(claim.now_t)}): "{claim.now_quote}"\n\n'
        f"LEDGER:\n{format_ledger(ledger)}\n\nTRANSCRIPT:\n{format_transcript(history)}\n\nReturn the JSON."
    )
    data = await (ask(prompt, SYSTEM) if ask else nebius.ask_json(prompt, SYSTEM, model))
    flag = data.get("is_contradiction")
    if not isinstance(flag, bool):
        raise ValueError("verifier: is_contradiction missing")
    try:
        conf = min(1.0, max(0.0, float(data.get("confidence"))))
    except (TypeError, ValueError) as e:
        raise ValueError("verifier: confidence missing") from e
    reason = data.get("reason")
    return Verification(flag, conf, reason.strip() if isinstance(reason, str) else "", model)


async def refine(
    analysis: Analysis, history: Sequence[Utterance], ledger: Sequence[LedgerItem], ask: Ask | None = None
) -> tuple[Analysis, Verification | None]:
    """Run the verifier when there is something to check. Returns the (possibly new) analysis and
    the verification (None if it did not run or failed)."""
    claim = claim_from(analysis, history)
    if claim is None:
        return analysis, None
    try:
        v = await verify(claim, history, ledger, ask)
    except Exception as e:  # keep Gemma's result, but never let it fire a public interjection
        log.warning("verifier failed: %s", type(e).__name__)
        c = analysis.contradiction
        if c and c.confidence > UNVERIFIED_CAP:
            analysis = replace(analysis, contradiction=replace(c, confidence=UNVERIFIED_CAP))
        return analysis, None
    if v.is_contradiction:
        c = Contradiction(claim.now_quote, claim.then_quote, claim.then_id, v.confidence)
        return replace(analysis, contradiction=c), v
    return replace(analysis, contradiction=None), v
