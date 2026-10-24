"""ElevenLabs Scribe Realtime: one websocket per channel, VAD-committed segments."""
import asyncio
import base64
import json
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import websockets
from dotenv import load_dotenv

from pinoqio.events import Speaker
from pinoqio.prosody import SR, trim_silence

log = logging.getLogger(__name__)

URL = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"
MODEL = "scribe_v2_realtime"
VAD_SILENCE_SECS = 0.7
FLUSH_WAIT = 5.0  # seconds to wait for the final commit once input ends
RECONNECT_DELAY = 1.0
_ERROR_TYPES = {
    "error", "auth_error", "quota_exceeded", "commit_throttled", "unaccepted_terms",
    "rate_limited", "queue_overflow", "resource_exhausted", "session_time_limit_exceeded",
    "input_error", "invalid_request", "chunk_size_exceeded", "transcriber_error",
}


@dataclass(frozen=True)
class Segment:
    """One committed transcript segment; audio is trimmed to the voiced span."""

    speaker: Speaker
    text: str
    audio: np.ndarray
    t_start: float  # seconds since this channel's stream start
    t_end: float


def api_key() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(os.environ.get("PINOQIO_ENV_FILE", repo_root / ".env"))
    try:
        return os.environ["ELEVENLABS_API_KEY"]
    except KeyError:
        raise RuntimeError("ELEVENLABS_API_KEY is not set") from None


def _url() -> str:
    query = {
        "model_id": MODEL,
        "audio_format": "pcm_16000",
        "commit_strategy": "vad",
        "vad_silence_threshold_secs": VAD_SILENCE_SECS,
    }
    return f"{URL}?{urlencode(query)}"


class _Buffer:
    """Audio sent since the last commit, plus its offset from stream start (internal state)."""

    def __init__(self):
        self._chunks: list[np.ndarray] = []
        self._base = 0

    def add(self, chunk: np.ndarray) -> None:
        self._chunks.append(chunk)

    def take(self, speaker: Speaker, text: str) -> Segment:
        audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, np.int16)
        base = self._base
        self._chunks = []
        self._base += len(audio)
        start, end = trim_silence(audio)
        return Segment(speaker, text, audio[start:end], (base + start) / SR, (base + end) / SR)


def _chunk_msg(chunk: np.ndarray, commit: bool) -> str:
    return json.dumps({
        "message_type": "input_audio_chunk",
        "audio_base_64": base64.b64encode(chunk.tobytes()).decode(),
        "commit": commit,
        "sample_rate": SR,
    })


async def _send(ws, chunks, buf: _Buffer, done: asyncio.Event) -> None:
    async for chunk in chunks:
        buf.add(chunk)
        await ws.send(_chunk_msg(chunk, commit=False))
    await ws.send(_chunk_msg(np.zeros(SR // 10, np.int16), commit=True))  # flush the tail
    done.set()


async def _recv(ws, speaker: Speaker, buf: _Buffer, done: asyncio.Event, out: asyncio.Queue) -> None:
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), FLUSH_WAIT if done.is_set() else 1.0)
        except TimeoutError:
            if done.is_set():
                return
            continue
        msg = json.loads(raw)
        kind = msg.get("message_type")
        if kind == "committed_transcript":
            text = msg.get("text", "").strip()
            if text:
                await out.put(buf.take(speaker, text))
        elif kind in _ERROR_TYPES:
            log.warning("scribe %s (%s): %s", speaker, kind, msg.get("error"))


async def _run(chunks, speaker: Speaker, connect, key: str, buf: _Buffer, out: asyncio.Queue) -> None:
    done = asyncio.Event()
    while not done.is_set():
        try:
            async with connect(_url(), additional_headers={"xi-api-key": key}) as ws:
                sender = asyncio.create_task(_send(ws, chunks, buf, done))
                try:
                    await _recv(ws, speaker, buf, done, out)
                finally:
                    sender.cancel()
        except Exception as exc:  # a failed call must not crash the live pipeline
            log.warning("scribe %s connection failed: %s; retrying", speaker, exc)
            await asyncio.sleep(RECONNECT_DELAY)


async def segments(
    chunks, speaker: Speaker, *, connect=websockets.connect, key: str | None = None
) -> AsyncIterator[Segment]:
    """Stream committed segments for one channel until `chunks` ends (replay) or forever (live)."""
    out: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(_run(chunks, speaker, connect, key or api_key(), _Buffer(), out))
    task.add_done_callback(lambda _: out.put_nowait(None))
    try:
        while (seg := await out.get()) is not None:
            yield seg
        task.result()
    finally:
        task.cancel()
