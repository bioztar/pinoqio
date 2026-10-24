"""Replay fallback: a wav file as the same 16 kHz mono int16 chunk stream live capture gives."""
import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 16_000
CHUNK = SR // 10  # 100 ms


def load_wav(path: Path) -> np.ndarray:
    """Read any wav as 16 kHz mono int16."""
    data, rate = sf.read(str(path), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    if rate != SR:
        # ponytail: linear interpolation, fine for speech; use soxr/scipy if quality matters
        n = int(round(len(mono) * SR / rate))
        mono = np.interp(np.linspace(0, len(mono) - 1, n), np.arange(len(mono)), mono)
    return (np.clip(mono, -1.0, 1.0) * 32767).astype(np.int16)


async def wav_chunks(path: Path, realtime: bool = True) -> AsyncIterator[np.ndarray]:
    """Yield 100 ms chunks, paced in real time unless `realtime` is False."""
    audio = load_wav(path)
    for i in range(0, len(audio), CHUNK):
        yield audio[i : i + CHUNK]
        await asyncio.sleep(CHUNK / SR if realtime else 0)
