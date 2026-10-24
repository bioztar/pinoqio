"""Entry point: uv run python -m pinoqio.app --source fake|live|replay [--them-wav X --me-wav Y] [--no-window]"""
import argparse
import asyncio
import logging
import socket
import threading
import time
from collections.abc import AsyncIterator

import uvicorn

from pinoqio import fake
from pinoqio.events import Utterance, Verdict
from pinoqio.record import recording
from pinoqio.server import Hub, create_app

log = logging.getLogger("pinoqio.app")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def with_voice_hook(stream: AsyncIterator[Utterance | Verdict]) -> AsyncIterator[Utterance | Verdict]:
    """Pass events through; hand verdicts to the voice lane's auto policy if it exists."""
    try:
        from pinoqio.voice import on_verdict
    except (ImportError, AttributeError):
        on_verdict = None
    async for event in stream:
        if on_verdict and isinstance(event, Verdict):
            try:
                result = on_verdict(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                log.exception("voice.on_verdict failed")
        yield event


def make_source(args: argparse.Namespace):
    async def fake_source(_: Hub):
        async for e in with_voice_hook(fake.events(args.speed)):
            yield e

    async def pipeline_source(hub: Hub):
        # Lazy: ears/brain land in other lanes. ponytail: assumes ears.utterances(**wavs) / brain.verdicts(stream).
        from pinoqio import brain, ears
        wavs = {"them_wav": args.them_wav, "me_wav": args.me_wav} if args.source == "replay" else {}
        # brain.verdicts yields the utterances too, so no tee into the hub
        async for v in with_voice_hook(brain.verdicts(ears.utterances(args.source, **wavs))):
            yield v

    source = fake_source if args.source == "fake" else pipeline_source
    if not args.record:
        return source
    return lambda hub: recording(source(hub), args.record)


def main() -> None:
    p = argparse.ArgumentParser(prog="pinoqio")
    p.add_argument("--source", choices=["fake", "live", "replay"], default="fake")
    p.add_argument("--them-wav")
    p.add_argument("--me-wav")
    p.add_argument("--no-window", action="store_true")
    p.add_argument("--record", metavar="PATH.jsonl", help="write every event with its time offset (feeds the web demo)")
    p.add_argument("--speed", type=float, default=1.0, help="fake source playback speed")
    args = p.parse_args()
    if args.source == "replay" and not (args.them_wav and args.me_wav):
        p.error("--source replay needs --them-wav and --me-wav")

    logging.basicConfig(level=logging.INFO)
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(make_source(args)), host="127.0.0.1", port=port, log_level="warning"))
    url = f"http://127.0.0.1:{port}"

    if args.no_window:
        print(f"Pinoqio at {url}")
        server.run()
        return

    from pinoqio.window import run_window
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    try:
        run_window(url)  # blocks until the window closes
    finally:
        server.should_exit = True
        thread.join(timeout=3)


if __name__ == "__main__":
    main()
