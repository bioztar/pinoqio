import time

import numpy as np
import soundfile as sf

from pinoqio import replay


def write_wav(path, secs=0.5, rate=16_000):
    t = np.arange(int(rate * secs)) / rate
    sf.write(str(path), 0.5 * np.sin(2 * np.pi * 200 * t), rate, subtype="PCM_16")


async def test_chunks_are_100ms_int16(tmp_path):
    wav = tmp_path / "a.wav"
    write_wav(wav)
    chunks = [c async for c in replay.wav_chunks(wav, realtime=False)]
    assert len(chunks) == 5 and all(c.dtype == np.int16 and len(c) == 1600 for c in chunks)


async def test_resamples_to_16k(tmp_path):
    wav = tmp_path / "a.wav"
    write_wav(wav, secs=1.0, rate=44_100)
    assert len(replay.load_wav(wav)) == 16_000


async def test_realtime_pacing(tmp_path):
    wav = tmp_path / "a.wav"
    write_wav(wav, secs=0.5)
    t0 = time.monotonic()
    _ = [c async for c in replay.wav_chunks(wav, realtime=True)]
    assert time.monotonic() - t0 >= 0.45
