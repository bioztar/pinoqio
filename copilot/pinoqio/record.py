"""Record an event stream to JSONL (one line per event with its time offset) and play it back with the same timing."""
import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

from pinoqio.events import Utterance, Verdict
from pinoqio.server import to_json


async def recording(
    stream: AsyncIterator[Utterance | Verdict], path: str | Path, clock: Callable[[], float] = time.monotonic
) -> AsyncIterator[Utterance | Verdict]:
    """Pass events through, writing `{"t": seconds_since_start, **to_json(event)}` per line."""
    t0 = clock()
    with Path(path).open("w", encoding="utf-8") as f:
        async for event in stream:
            f.write(json.dumps({"t": round(clock() - t0, 3), **to_json(event)}) + "\n")
            f.flush()
            yield event


def load(path: str | Path) -> tuple[dict, ...]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return tuple(json.loads(line) for line in lines if line.strip())


async def play(
    events: tuple[dict, ...],
    send: Callable[[dict], Awaitable[None]],
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Send each event (minus its `t`) at its recorded offset; absolute timing so sends never drift."""
    start = clock()
    for event in events:
        await sleep(max(0.0, event["t"] - (clock() - start)))
        await send({k: v for k, v in event.items() if k != "t"})
