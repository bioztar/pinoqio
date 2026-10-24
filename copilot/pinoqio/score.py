"""Combine verbal (Gemma) and vocal (prosody) cues into a Verdict. Pure, no I/O.

Weights are logit increments. Rationale:
- Verbal content cues beat vocal ones. Contradiction is the strongest signal, then number
  drift, evasion, hedging.
- Vocal effect sizes are small: pitch d~0.27, response latency d~0.18 (Sporer & Schwandt 2006);
  most nonverbal cues are weak (DePaulo et al. 2003). So vocal gets a small per-cue weight and
  a hard cap on the total.
- Best multimodal deception detection is ~65% (DOLOS, ICCV 2023), so never show > 95%.
"""
import math
from dataclasses import dataclass

from pinoqio.analyst import Analysis
from pinoqio.events import Chip, Verdict

BIAS = -2.0           # prior: ~12% when no cue fires
W_CONTRADICTION = 4.0  # x confidence
W_DRIFT = 2.0
W_EVASION = 1.8      # x score
W_HEDGING = 1.0       # x score
VOCAL_CAP = 0.8       # max total logit from all vocal cues
MAX_PROB = 0.95
MIN_CHIP_LOGIT = 0.3  # contributors below this are noise, no chip
Z_MIN, Z_MAX = 1.0, 3.0  # ignore |z| < 1, clip at 3

# (prosody z key, chip kind, weight per z, direction: 1 = only increases, 0 = either way, label)
VOCAL_CUES = (
    ("pitch_mean_hz_z", "pitch", 0.20, 1, "Pitch up {z:.1f}σ vs their baseline"),
    ("latency_s_z", "latency", 0.15, 1, "Slow to answer ({z:.1f}σ above their norm)"),
    ("pause_ratio_z", "pause", 0.12, 1, "More pauses than usual ({z:.1f}σ)"),
    ("rate_wps_z", "rate", 0.10, 0, "Speech rate shifted {z:.1f}σ"),
    ("filler_count_z", "filler", 0.10, 1, "More fillers than usual ({z:.1f}σ)"),
)


@dataclass(frozen=True)
class _Cue:
    chip: Chip
    logit: float


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _clock(t: float | None) -> str:
    return "" if t is None else f" at {int(t // 60)}:{int(t % 60):02d}"


def _chip(kind, label: str, logit: float, quote: str | None = None) -> Chip:
    return Chip(kind, label, round(min(1.0, logit / 4.0), 3), quote)


def _verbal_cues(a: Analysis) -> tuple[_Cue, ...]:
    cues: list[_Cue] = []
    if a.contradiction:
        c = a.contradiction
        logit = W_CONTRADICTION * c.confidence
        cues.append(_Cue(_chip("contradiction", f'Said "{c.then_quote}", now "{c.now_quote}"', logit, c.now_quote), logit))
    if a.number_drift:
        d = a.number_drift
        label = f"{d.item.capitalize()}: {d.then_value}{_clock(d.then_t)}, now {d.now_value}"
        cues.append(_Cue(_chip("number_drift", label, W_DRIFT), W_DRIFT))
    if a.evasion > 0:
        logit = W_EVASION * a.evasion
        cues.append(_Cue(_chip("evasion", a.evasion_why or "Dodged the question", logit), logit))
    if a.hedging > 0:
        logit = W_HEDGING * a.hedging
        quote = ", ".join(a.hedge_phrases) or None
        cues.append(_Cue(_chip("hedging", f"Hedging: {quote}" if quote else "Hedging language", logit, quote), logit))
    return tuple(cues)


def _vocal_cues(prosody: dict[str, float]) -> tuple[_Cue, ...]:
    raw: list[_Cue] = []
    for key, kind, weight, one_way, label in VOCAL_CUES:
        z = prosody.get(key, 0.0)
        z = z if one_way else abs(z)
        if z < Z_MIN:
            continue
        logit = weight * min(z, Z_MAX)
        raw.append(_Cue(_chip(kind, label.format(z=z), logit), logit))
    total = sum(c.logit for c in raw)
    scale = VOCAL_CAP / total if total > VOCAL_CAP else 1.0
    return tuple(_Cue(_chip(c.chip.kind, c.chip.label, c.logit * scale), c.logit * scale) for c in raw)


def score(analysis: Analysis, prosody: dict[str, float]) -> Verdict:
    verbal, vocal = _verbal_cues(analysis), _vocal_cues(prosody)
    verbal_logit = sum(c.logit for c in verbal)
    vocal_logit = sum(c.logit for c in vocal)
    chips = tuple(c.chip for c in sorted(verbal + vocal, key=lambda c: -c.logit) if c.logit >= MIN_CHIP_LOGIT)
    return Verdict(
        utterance_id=analysis.utterance_id,
        probability=round(min(MAX_PROB, _sigmoid(BIAS + verbal_logit + vocal_logit)), 3),
        verbal=round(_sigmoid(BIAS + verbal_logit), 3),
        vocal=round(_sigmoid(BIAS + vocal_logit), 3),
        chips=chips,
        contradiction=analysis.contradiction,
        ask_next=analysis.ask_next,
    )
