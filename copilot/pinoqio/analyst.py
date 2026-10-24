"""Verbal-cue analyst: one Gemma call per counterparty utterance -> structured Analysis."""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Sequence

from pinoqio.events import Contradiction, LedgerItem, Utterance
from pinoqio.gemma import ask_json

log = logging.getLogger(__name__)

SYSTEM = (Path(__file__).parent / "prompts" / "analyst.md").read_text()
WINDOW = 12  # transcript lines in the analyst prompt

Ask = Callable[[str, str | None], Awaitable[dict]]


@dataclass(frozen=True)
class NumberDrift:
    item: str
    then_value: str
    now_value: str
    then_t: float | None = None  # seconds when the earlier value was said
    then_id: int | None = None


@dataclass(frozen=True)
class Analysis:
    utterance_id: int = -1
    contradiction: Contradiction | None = None
    evasion: float = 0.0
    evasion_why: str = ""
    number_drift: NumberDrift | None = None
    hedging: float = 0.0
    hedge_phrases: tuple[str, ...] = ()
    ledger_updates: tuple[LedgerItem, ...] = ()
    ask_next: str | None = None


def _norm(s: str) -> str:
    return " ".join(s.casefold().split())


def _is_quote(quote: str, text: str) -> bool:
    q = _norm(quote)
    return bool(q) and q in _norm(text)


def _unit(v: Any) -> float:
    try:
        return min(1.0, max(0.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


def _str(v: Any) -> str:
    return v.strip() if isinstance(v, str) else ""


def format_transcript(history: Sequence[Utterance]) -> str:
    return "\n".join(
        f"[{u.id}] {u.speaker.upper()} ({int(u.t_start // 60)}:{int(u.t_start % 60):02d}): {u.text}"
        for u in history
    )


def format_ledger(ledger: Sequence[LedgerItem]) -> str:
    if not ledger:
        return "(empty)"
    return "\n".join(f"- {i.who}: {i.item} = {i.value} (utterance {i.utterance_id})" for i in ledger)


def merge_ledger(ledger: Sequence[LedgerItem], updates: Sequence[LedgerItem]) -> tuple[LedgerItem, ...]:
    """New ledger: an update replaces the old entry with the same (who, item)."""
    keys = {(u.who, _norm(u.item)) for u in updates}
    kept = tuple(i for i in ledger if (i.who, _norm(i.item)) not in keys)
    return kept + tuple(updates)


def _contradiction(raw: Any, current: Utterance, history: Sequence[Utterance]) -> Contradiction | None:
    if not isinstance(raw, dict):
        return None
    then_id = raw.get("then_utterance_id")
    then = next((u for u in history if u.id == then_id and u.speaker == "them" and u.id < current.id), None)
    now_q, then_q = _str(raw.get("now_quote")), _str(raw.get("then_quote"))
    if then is None or not _is_quote(now_q, current.text) or not _is_quote(then_q, then.text):
        return None
    return Contradiction(now_q, then_q, then.id, _unit(raw.get("confidence")))


def _drift(raw: Any, history: Sequence[Utterance]) -> NumberDrift | None:
    if not isinstance(raw, dict):
        return None
    item, then_v, now_v = _str(raw.get("item")), _str(raw.get("then_value")), _str(raw.get("now_value"))
    if not (item and then_v and now_v) or _norm(then_v) == _norm(now_v):
        return None
    then = next((u for u in history if u.id == raw.get("then_utterance_id")), None)
    return NumberDrift(item, then_v, now_v, then.t_start if then else None, then.id if then else None)


def _ledger_updates(raw: Any, uid: int) -> tuple[LedgerItem, ...]:
    if not isinstance(raw, list):
        return ()
    out = []
    for r in raw:
        if isinstance(r, dict) and r.get("who") in ("me", "them") and _str(r.get("item")) and _str(r.get("value")):
            out.append(LedgerItem(r["who"], _str(r["item"]), _str(r["value"]), uid))
    return tuple(out)


def parse_analysis(data: dict, history: Sequence[Utterance]) -> Analysis:
    """Validate Gemma's JSON against the transcript; anything unsupported is dropped."""
    current = history[-1]
    evasion = data.get("evasion") if isinstance(data.get("evasion"), dict) else {}
    hedging = data.get("hedging") if isinstance(data.get("hedging"), dict) else {}
    phrases = hedging.get("phrases")
    return Analysis(
        utterance_id=current.id,
        contradiction=_contradiction(data.get("contradiction"), current, history[:-1]),
        evasion=_unit(evasion.get("score")),
        evasion_why=_str(evasion.get("why")),
        number_drift=_drift(data.get("number_drift"), history[:-1]),
        hedging=_unit(hedging.get("score")),
        hedge_phrases=tuple(p.strip() for p in phrases if isinstance(p, str)) if isinstance(phrases, list) else (),
        ledger_updates=_ledger_updates(data.get("ledger_updates"), current.id),
        ask_next=_str(data.get("ask_next")) or None,
    )


async def analyze(
    history: Sequence[Utterance], ledger: Sequence[LedgerItem], ask: Ask = ask_json
) -> Analysis:
    """Analyse history[-1] (a 'them' utterance). Raises GemmaError if the call fails.

    The prompt carries only the last WINDOW lines plus the full ledger (it holds earlier numbers
    with their utterance ids), so it stops growing over the call. Validation uses the full history."""
    prompt = (
        f"TRANSCRIPT (recent lines; ledger entries may cite earlier utterance ids):\n"
        f"{format_transcript(history[-WINDOW:])}\n\nLEDGER:\n{format_ledger(ledger)}\n\n"
        f"Current utterance id: {history[-1].id}. Return the JSON."
    )
    log.info("analyst prompt ~%d tokens (%d lines)", (len(prompt) + len(SYSTEM)) // 4, min(len(history), WINDOW))
    return parse_analysis(await ask(prompt, SYSTEM), history)
