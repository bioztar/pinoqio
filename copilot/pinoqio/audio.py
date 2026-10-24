"""Live capture: two sounddevice input streams -> 16 kHz mono int16 chunks."""
import asyncio
import os
import threading
import time
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import numpy as np
import sounddevice as sd

SR = 16_000
CHUNK = SR // 10  # 100 ms

DEFAULT_THEM = "BlackHole 2ch"
DEFAULT_ME = "MacBook Air Microphone"


class DeviceNotFound(RuntimeError):
    pass


# Set by pinoqio.voice while a clip plays out loud, so the mic doesn't hear Pinoqio as a speaker.
SPEAKING = threading.Event()


def find_device(name: str) -> tuple[int, int]:
    """(index, input channels) of the first input device whose name contains `name`."""
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0 and name.lower() in dev["name"].lower():
            return i, dev["max_input_channels"]
    inputs = [d["name"] for d in devices if d["max_input_channels"] > 0]
    raise DeviceNotFound(f"audio input device {name!r} not found; inputs: {inputs}")


def device_names() -> tuple[str, str]:
    return (
        os.environ.get("PINOQIO_THEM_DEVICE", DEFAULT_THEM),
        os.environ.get("PINOQIO_ME_DEVICE", DEFAULT_ME),
    )


def to_mono_int16(block: np.ndarray) -> np.ndarray:
    """(frames, channels) int16 -> (frames,) int16 by channel mean."""
    return block.astype(np.int32).mean(axis=1).astype(np.int16)


# Echo duck: when the far end plays through the laptop speakers, the laptop mic hears it too and
# would transcribe the seller as the buyer. While THEM is loud (and for a short tail), ME is muted.
# ponytail: energy gate, not real echo cancellation; set PINOQIO_DUCK=0 when using headphones.
DUCK = os.environ.get("PINOQIO_DUCK", "1") != "0"
DUCK_RMS = 300.0       # int16 RMS that counts as the far end talking
DUCK_TAIL_S = 0.35     # keep the mic muted this long after they stop (speaker/room latency)
_them_loud_until = [0.0]


def _rms(block: np.ndarray) -> float:
    return float(np.sqrt(np.mean(block.astype(np.float64) ** 2))) if block.size else 0.0


@asynccontextmanager
async def _open(name: str, role: str = "") -> AsyncIterator[asyncio.Queue]:
    index, channels = find_device(name)
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def callback(indata, frames, time_info, status):
        block = to_mono_int16(indata)
        now = time.monotonic()
        if role == "them" and _rms(block) > DUCK_RMS:
            _them_loud_until[0] = now + DUCK_TAIL_S
        if SPEAKING.is_set():  # Pinoqio is talking through the speakers: don't transcribe itself
            block = np.zeros_like(block)
        elif role == "me" and DUCK and now < _them_loud_until[0]:
            block = np.zeros_like(block)
        loop.call_soon_threadsafe(queue.put_nowait, block)

    stream = sd.InputStream(
        device=index, samplerate=SR, channels=min(channels, 2),
        dtype="int16", blocksize=CHUNK, callback=callback,
    )
    stream.start()
    try:
        yield queue
    finally:
        stream.stop()
        stream.close()


class QueueChunks:
    """Async iterator over a queue. Not a generator, so a cancelled read doesn't end it."""

    def __init__(self, queue: asyncio.Queue):
        self._queue = queue

    def __aiter__(self):
        return self

    async def __anext__(self) -> np.ndarray:
        return await self._queue.get()


@asynccontextmanager
async def open_pair() -> AsyncIterator[tuple[AsyncIterator[np.ndarray], AsyncIterator[np.ndarray]]]:
    """Yield (them_chunks, me_chunks) async iterators; streams close on exit."""
    them_name, me_name = device_names()
    async with AsyncExitStack() as stack:
        them_q = await stack.enter_async_context(_open(them_name, "them"))
        me_q = await stack.enter_async_context(_open(me_name, "me"))
        yield QueueChunks(them_q), QueueChunks(me_q)
