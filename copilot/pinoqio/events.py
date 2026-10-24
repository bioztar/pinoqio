"""Contract between lanes. ears emits Utterance, brain emits Verdict, face renders both.

Change this file only through its own PR; every lane imports it.
"""
from dataclasses import dataclass, field
from typing import Literal

Speaker = Literal["me", "them"]
ChipKind = Literal[
    "contradiction", "evasion", "number_drift", "hedging",
    "pitch", "pause", "latency", "rate", "filler",
]


@dataclass(frozen=True)
class Utterance:
    id: int
    speaker: Speaker
    text: str
    t_start: float  # seconds since session start
    t_end: float
    # pitch_mean_hz, pitch_sd_hz, rate_wps, pause_ratio, latency_s, filler_count,
    # plus *_z keys: z-score against this speaker's own running baseline. May be empty.
    prosody: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Chip:
    kind: ChipKind
    label: str            # short human text, e.g. "Price was 40k at 0:42, now 48k"
    weight: float         # contribution to probability, 0..1
    quote: str | None = None


@dataclass(frozen=True)
class Contradiction:
    now_quote: str
    then_quote: str
    then_utterance_id: int
    confidence: float     # 0..1; public interjection only at >= 0.85


@dataclass(frozen=True)
class LedgerItem:
    who: Speaker
    item: str             # e.g. "delivery date", "unit price"
    value: str            # e.g. "15 March", "40k EUR"
    utterance_id: int


@dataclass(frozen=True)
class Verdict:
    utterance_id: int
    probability: float    # 0..1 likelihood the utterance is deceptive or evasive
    verbal: float         # 0..1 verbal-cue score (Gemma)
    vocal: float          # 0..1 vocal-cue score (prosody vs baseline)
    chips: tuple[Chip, ...] = ()
    contradiction: Contradiction | None = None
    ledger: tuple[LedgerItem, ...] = ()   # full ledger after this utterance
    ask_next: str | None = None
