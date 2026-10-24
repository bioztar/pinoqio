"""Smoke test for the ears lane.

  uv run python scripts/smoke_ears.py live [seconds]
  uv run python scripts/smoke_ears.py replay THEM.wav ME.wav [--fast]

Needs PINOQIO_ENV_FILE (or a repo-root .env) providing ELEVENLABS_API_KEY.
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pinoqio.ears import utterances  # noqa: E402


async def run(args) -> None:
    if args.mode == "live":
        stream = utterances("live")
    else:
        stream = utterances("replay", args.them, args.me, realtime=not args.fast)
    try:
        async with asyncio.timeout(args.seconds if args.mode == "live" else None):
            async for u in stream:
                prosody = {k: round(v, 2) for k, v in u.prosody.items() if not k.endswith("_z")}
                print(f"#{u.id} [{u.speaker}] {u.t_start:.1f}-{u.t_end:.1f}s {u.text!r} {prosody}", flush=True)
    except TimeoutError:
        print("done (time limit)")
    finally:
        await stream.aclose()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["live", "replay"])
    p.add_argument("them", nargs="?", type=Path)
    p.add_argument("me", nargs="?", type=Path)
    p.add_argument("--fast", action="store_true", help="replay faster than real time")
    p.add_argument("--seconds", type=float, default=30)
    args = p.parse_args()
    if args.mode == "live" and args.them:
        args.seconds = float(str(args.them))  # `live 45` shorthand
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
