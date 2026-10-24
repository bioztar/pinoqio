"""Synthesize demo/script.md into aligned replay wavs: demo/replay/me.wav and them.wav.

Run once: PINOQIO_ENV_FILE=<.env> uv run python demo/make_replay.py
Both files are 16 kHz mono int16 and exactly the same length (one shared timeline).
"""
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # so `pinoqio` imports when run as a script

RATE = 16000
LINE_RE = re.compile(r"^(\d+)\. \*\*(BUYER|SUPPLIER)\*\* \[(\d+(?:\.\d+)?)\]: (.+)$")
# premade ElevenLabs voices; override with env if the account lacks them
VOICES = {
    "BUYER": os.environ.get("PINOQIO_VOICE_ME", "pNInz6obpgDQGcFmaJgB"),        # Adam
    "SUPPLIER": os.environ.get("PINOQIO_VOICE_THEM", "TxGEqnHWrfWFTfGW9XjX"),   # Josh
}
CHANNEL = {"BUYER": "me", "SUPPLIER": "them"}


@dataclass(frozen=True)
class Line:
    n: int
    role: str
    gap_s: float
    text: str


def parse_script(md: str) -> tuple[Line, ...]:
    return tuple(
        Line(int(m[1]), m[2], float(m[3]), m[4])
        for m in map(LINE_RE.match, md.splitlines()) if m
    )


def build_timeline(lines: tuple[Line, ...], clips: dict[int, np.ndarray]) -> dict[str, np.ndarray]:
    """Lay clips end to end with their gaps; return equal-length int16 arrays per channel."""
    cursor, placed = 0, []
    for ln in lines:
        start = cursor + round(ln.gap_s * RATE)
        placed.append((CHANNEL[ln.role], start, clips[ln.n]))
        cursor = start + len(clips[ln.n])
    total = cursor + RATE  # 1 s tail
    out = {"me": np.zeros(total, dtype=np.int16), "them": np.zeros(total, dtype=np.int16)}
    for ch, start, pcm in placed:
        out[ch][start:start + len(pcm)] = pcm
    return out


def main() -> None:
    from pinoqio.voice import synth_pcm  # imported late: pulls sounddevice

    lines = parse_script((HERE / "script.md").read_text())
    if not lines:
        raise SystemExit("no spoken lines found in script.md")
    clips = {}
    for ln in lines:
        print(f"synth {ln.n}/{len(lines)} {ln.role}", flush=True)
        clips[ln.n] = synth_pcm(ln.text, VOICES[ln.role], rate=RATE)
    out = build_timeline(lines, clips)
    (HERE / "replay").mkdir(exist_ok=True)
    for ch, pcm in out.items():
        sf.write(HERE / "replay" / f"{ch}.wav", pcm, RATE, subtype="PCM_16")
    print(f"wrote me.wav + them.wav, {len(out['me']) / RATE:.1f}s")


if __name__ == "__main__":
    main()
