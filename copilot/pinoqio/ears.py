"""Ears lane entry point: two audio channels -> Scribe -> prosody -> Utterance stream."""
import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Literal

from pinoqio import audio, prosody, replay, stt
from pinoqio.events import Speaker, Utterance

log = logging.getLogger(__name__)


async def _pump(speaker: Speaker, chunks, segments_fn, out: asyncio.Queue) -> None:
    try:
        async for seg in segments_fn(chunks, speaker):
            await out.put(seg)
    except Exception:
        log.exception("ears: %s channel stopped", speaker)
    finally:
        await out.put(None)


def _to_utterance(uid: int, seg: stt.Segment, baseline: prosody.Baseline, last_me_end: float | None):
    """(Utterance, new baseline) for one segment."""
    feats = prosody.extract(seg.audio, seg.text)
    if seg.speaker == "them" and last_me_end is not None:
        feats = {**feats, "latency_s": max(0.0, seg.t_start - last_me_end)}
    utt = Utterance(uid, seg.speaker, seg.text, seg.t_start, seg.t_end, prosody.with_z(feats, baseline))
    return utt, baseline.update(feats)


async def utterances(
    source: Literal["live", "replay", "stream"],
    them_wav: Path | None = None,
    me_wav: Path | None = None,
    *,
    realtime: bool = True,
    segments_fn=stt.segments,
    streams: tuple[AsyncIterator, AsyncIterator] | None = None,
) -> AsyncIterator[Utterance]:
    """`stream` = caller supplies `streams=(them, me)` 16 kHz mono int16 chunk iterators (web live mode)."""
    if source == "replay" and (them_wav is None or me_wav is None):
        raise ValueError("replay needs both them_wav and me_wav")
    if source == "stream" and streams is None:
        raise ValueError("stream needs streams=(them, me)")
    if source not in ("live", "replay", "stream"):
        raise ValueError(f"unknown source {source!r}")

    async with AsyncExitStack() as stack:
        if source == "stream":
            them, me = streams
        elif source == "live":
            them, me = await stack.enter_async_context(audio.open_pair())
        else:
            them, me = replay.wav_chunks(them_wav, realtime), replay.wav_chunks(me_wav, realtime)

        out: asyncio.Queue = asyncio.Queue()
        pumps = [
            asyncio.create_task(_pump("them", them, segments_fn, out)),
            asyncio.create_task(_pump("me", me, segments_fn, out)),
        ]
        baselines = {"them": prosody.Baseline(), "me": prosody.Baseline()}
        last_me_end: float | None = None
        open_channels, uid = len(pumps), 0
        try:
            while open_channels:
                seg = await out.get()
                if seg is None:
                    open_channels -= 1
                    continue
                uid += 1
                utt, new_base = _to_utterance(uid, seg, baselines[seg.speaker], last_me_end)
                baselines = {**baselines, seg.speaker: new_base}
                if seg.speaker == "me":
                    last_me_end = seg.t_end
                yield utt
        finally:
            for p in pumps:
                p.cancel()
