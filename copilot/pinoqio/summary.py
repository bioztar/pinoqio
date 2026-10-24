"""Post-call summary (Nebius): commitments, open questions, red flags with quotes, next email.

Input is the event stream of the call (Utterance / Verdict objects or their JSON dicts). If Nebius
fails, an offline summary is built from the ledger and the flagged contradictions.
"""
import dataclasses
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable

from pinoqio import config, nebius
from pinoqio.analyst import _norm

log = logging.getLogger(__name__)

SYSTEM = (Path(__file__).parent / "prompts" / "summary.md").read_text()
TIMEOUT_S = 20.0  # bigger prompt and output than the per-utterance calls
MAX_FLAGS = 5

Ask = Callable[[str, str | None], Awaitable[dict]]


@dataclass(frozen=True)
class Commitment:
    who: str
    item: str
    value: str
    changed: bool = False
    was: str | None = None


@dataclass(frozen=True)
class RedFlag:
    text: str
    quote: str | None = None


@dataclass(frozen=True)
class Summary:
    commitments: tuple[Commitment, ...] = ()
    open_questions: tuple[str, ...] = ()
    red_flags: tuple[RedFlag, ...] = ()
    next_email: str = ""
    model: str = ""


@dataclass(frozen=True)
class Digest:
    lines: tuple[tuple[int, str, float, str], ...]  # (id, speaker, t_start, text)
    ledger: tuple[dict, ...]
    contradictions: tuple[tuple[str, str], ...]  # (then_quote, now_quote), de-duplicated


def _as_dict(e: Any) -> dict:
    return dataclasses.asdict(e) if dataclasses.is_dataclass(e) else e


def digest(events: Iterable[Any]) -> Digest:
    lines, ledger, contras = [], (), []
    for d in map(_as_dict, events):
        if "text" in d and "speaker" in d:
            lines.append((d["id"], d["speaker"], d["t_start"], d["text"]))
        elif "probability" in d:
            ledger = tuple(d.get("ledger") or ())
            c = d.get("contradiction")
            if c and (c["then_quote"], c["now_quote"]) not in contras:
                contras.append((c["then_quote"], c["now_quote"]))
    return Digest(tuple(lines), ledger, tuple(contras))


def _clock(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def _prompt(d: Digest) -> str:
    transcript = "\n".join(f"[{i}] {s.upper()} ({_clock(t)}): {x}" for i, s, t, x in d.lines)
    ledger = "\n".join(f"- {r['who']}: {r['item']} = {r['value']}" for r in d.ledger) or "(empty)"
    flagged = "\n".join(f'- earlier "{a}" / later "{b}"' for a, b in d.contradictions) or "(none)"
    return f"TRANSCRIPT:\n{transcript}\n\nFINAL LEDGER:\n{ledger}\n\nFLAGGED CONTRADICTIONS:\n{flagged}\n\nReturn the JSON."


def _s(v: Any) -> str:
    return v.strip() if isinstance(v, str) else ""


def parse(data: dict, d: Digest, model: str) -> Summary:
    """Validate Gemma-style: anything malformed is dropped, quotes must be verbatim THEM text."""
    them = _norm(" ".join(x for _, s, _, x in d.lines if s == "them"))
    commitments = tuple(
        Commitment(r["who"], _s(r["item"]), _s(r["value"]), r.get("changed") is True, _s(r.get("was")) or None)
        for r in (data.get("commitments") if isinstance(data.get("commitments"), list) else ())
        if isinstance(r, dict) and r.get("who") in ("me", "them") and _s(r.get("item")) and _s(r.get("value"))
    )
    flags = tuple(
        RedFlag(_s(r["text"]), q if (q := _s(r.get("quote"))) and _norm(q) in them else None)
        for r in (data.get("red_flags") if isinstance(data.get("red_flags"), list) else ())
        if isinstance(r, dict) and _s(r.get("text"))
    )[:MAX_FLAGS]
    questions = data.get("open_questions")
    return Summary(
        commitments,
        tuple(q.strip() for q in questions if isinstance(q, str) and q.strip()) if isinstance(questions, list) else (),
        flags,
        _s(data.get("next_email")),
        model,
    )


def offline(d: Digest) -> Summary:
    """No model: ledger as commitments, each flagged contradiction as a red flag."""
    return Summary(
        tuple(Commitment(r["who"], r["item"], r["value"]) for r in d.ledger),
        (),
        tuple(RedFlag(f'They said "{a}", later "{b}"', b) for a, b in d.contradictions)[:MAX_FLAGS],
        "",
        "offline",
    )


async def summarize(events: Iterable[Any], ask: Ask | None = None) -> Summary | None:
    """None if the call had no counterparty speech. Never raises."""
    d = digest(events)
    if not any(s == "them" for _, s, _, _ in d.lines):
        return None
    try:
        model = config.nebius_model()
        data = await (ask(_prompt(d), SYSTEM) if ask else nebius.ask_json(_prompt(d), SYSTEM, model, TIMEOUT_S))
        return parse(data, d, nebius.short_name(model))
    except Exception as e:
        log.warning("summary failed, using offline: %s", type(e).__name__)
        return offline(d)
