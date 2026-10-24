"""Web "Try live": a passcode-gated websocket session that runs browser audio through ears -> brain.

Wire format. Client -> server: first a JSON text `{"passcode": "..."}`; then binary frames, byte 0 = channel
(0 = me/mic, 1 = them/tab audio) followed by 16 kHz mono int16 little-endian PCM; text `stop` ends the call.
Server -> client: `{"type": "ready"}`, then utterance/verdict messages, then `{"type": "end"}` or `{"type": "error"}`.
"""
import asyncio
import hmac
import logging
from collections.abc import AsyncIterator, Callable

import numpy as np
from fastapi import WebSocket, WebSocketDisconnect

from pinoqio.server import to_json

log = logging.getLogger("pinoqio.live")
CAP_SECONDS = 5 * 60
ME, THEM = 0, 1


class LiveState:
    """One live session at a time (each one spends Scribe + Gemma quota)."""

    def __init__(self) -> None:
        self.busy = False


async def _chunks(q: asyncio.Queue) -> AsyncIterator[np.ndarray]:
    while (chunk := await q.get()) is not None:
        yield chunk


async def real_pipeline(them: AsyncIterator, me: AsyncIterator) -> AsyncIterator:
    from pinoqio import brain, config, ears, stt  # lazy: heavy deps
    config.gemini_key()  # fail fast and visibly if a key is missing, not as a silent Scribe retry loop
    stt.api_key()
    async for event in brain.verdicts(ears.utterances("stream", streams=(them, me))):
        yield event


async def _feed(sock: WebSocket, them_q: asyncio.Queue, me_q: asyncio.Queue) -> None:
    try:
        while True:
            msg = await sock.receive()
            if msg["type"] == "websocket.disconnect" or msg.get("text") == "stop":
                return
            data = msg.get("bytes")
            if data and len(data) > 1:
                q = them_q if data[0] == THEM else me_q
                q.put_nowait(np.frombuffer(data[1 : 1 + (len(data) - 1) // 2 * 2], dtype="<i2"))
    finally:
        them_q.put_nowait(None)
        me_q.put_nowait(None)


async def _send(sock: WebSocket, msg: dict) -> None:
    try:
        await sock.send_json(msg)
    except (WebSocketDisconnect, RuntimeError):
        pass


async def run_session(
    sock: WebSocket,
    passcode: str,
    state: LiveState,
    pipeline: Callable[[AsyncIterator, AsyncIterator], AsyncIterator] = real_pipeline,
    cap_seconds: float = CAP_SECONDS,
) -> None:
    await sock.accept()
    try:
        hello = await sock.receive_json()
    except (WebSocketDisconnect, ValueError):
        return
    given = str(hello.get("passcode", "")) if isinstance(hello, dict) else ""
    if not hmac.compare_digest(given.encode(), passcode.encode()):
        await _send(sock, {"type": "error", "message": "Wrong passcode."})
        await sock.close()
        return
    if state.busy:
        await _send(sock, {"type": "error", "message": "Another live session is running. Try again in a few minutes."})
        await sock.close()
        return

    state.busy = True
    them_q: asyncio.Queue = asyncio.Queue()
    me_q: asyncio.Queue = asyncio.Queue()
    feeder = asyncio.create_task(_feed(sock, them_q, me_q))
    try:
        await _send(sock, {"type": "ready"})
        async with asyncio.timeout(cap_seconds):
            async for event in pipeline(_chunks(them_q), _chunks(me_q)):
                await sock.send_json(to_json(event))
        await _send(sock, {"type": "end"})
    except TimeoutError:
        await _send(sock, {"type": "end", "reason": f"{int(cap_seconds // 60)} minute limit reached"})
    except (WebSocketDisconnect, RuntimeError):
        log.info("live client went away")
    except Exception as exc:
        log.exception("live session failed")
        await _send(sock, {"type": "error", "message": f"{type(exc).__name__}: {exc}"})
    finally:
        feeder.cancel()
        state.busy = False
        try:
            await sock.close()
        except RuntimeError:
            pass
