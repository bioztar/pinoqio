"""Prosody features for one utterance. Pure functions; no I/O."""
import math
import re
import statistics
from dataclasses import dataclass, field

import numpy as np

SR = 16_000
FRAME = SR // 50  # 20 ms
MIN_BASELINE = 3
SD_FLOOR = 1e-6
_FILLER_RE = re.compile(r"\b(?:um+|uh+|eh|well|like|you know|i mean)\b", re.IGNORECASE)


def _frame_rms(audio: np.ndarray) -> np.ndarray:
    n = len(audio) // FRAME
    if n == 0:
        return np.zeros(0)
    frames = audio[: n * FRAME].astype(np.float64).reshape(n, FRAME)
    return np.sqrt((frames**2).mean(axis=1))


def _silence_threshold(rms: np.ndarray) -> float:
    return max(0.1 * float(rms.max()), 50.0) if len(rms) else 50.0


def trim_silence(audio: np.ndarray) -> tuple[int, int]:
    """Sample range [start, end) of the voiced part; whole clip if nothing is voiced."""
    rms = _frame_rms(audio)
    voiced = np.flatnonzero(rms >= _silence_threshold(rms)) if len(rms) else []
    if len(voiced) == 0:
        return 0, len(audio)
    return int(voiced[0]) * FRAME, min(len(audio), (int(voiced[-1]) + 1) * FRAME)


def pause_ratio(audio: np.ndarray) -> float:
    """Share of 20 ms frames below the silence threshold, within the voiced span."""
    start, end = trim_silence(audio)
    rms = _frame_rms(audio[start:end])
    if len(rms) == 0:
        return 0.0
    return float((rms < _silence_threshold(rms)).mean())


def filler_count(text: str) -> int:
    return len(_FILLER_RE.findall(text))


def pitch_stats(audio: np.ndarray) -> dict[str, float]:
    """pitch_mean_hz / pitch_sd_hz over voiced frames; empty if nothing is voiced."""
    import parselmouth  # heavy import, keep local

    try:
        snd = parselmouth.Sound(audio.astype(np.float64) / 32768.0, sampling_frequency=SR)
        f0 = snd.to_pitch().selected_array["frequency"]
    except Exception:  # too-short clips make praat raise
        return {}
    voiced = f0[f0 > 0]
    if len(voiced) == 0:
        return {}
    return {"pitch_mean_hz": float(voiced.mean()), "pitch_sd_hz": float(voiced.std())}


def extract(audio: np.ndarray, text: str) -> dict[str, float]:
    """Raw features for a trimmed segment's int16 audio and its transcript."""
    seconds = len(audio) / SR
    words = len(text.split())
    return {
        **pitch_stats(audio),
        "rate_wps": words / seconds if seconds > 0 else 0.0,
        "pause_ratio": pause_ratio(audio),
        "filler_count": float(filler_count(text)),
    }


@dataclass(frozen=True)
class Baseline:
    """A speaker's past feature values. Immutable; `update` returns a new one."""

    samples: dict[str, tuple[float, ...]] = field(default_factory=dict)

    def update(self, feats: dict[str, float]) -> "Baseline":
        merged = {k: (*self.samples.get(k, ()), v) for k, v in feats.items()}
        return Baseline({**self.samples, **merged})


def with_z(feats: dict[str, float], baseline: Baseline) -> dict[str, float]:
    """feats plus `<key>_z` against the baseline; z = 0 until 3 prior samples exist."""
    z = {}
    for key, value in feats.items():
        past = baseline.samples.get(key, ())
        if len(past) < MIN_BASELINE:
            z[f"{key}_z"] = 0.0
        else:
            sd = max(statistics.pstdev(past), SD_FLOOR)
            z[f"{key}_z"] = (value - statistics.fmean(past)) / sd
    return {**feats, **{k: (0.0 if math.isnan(v) else v) for k, v in z.items()}}
