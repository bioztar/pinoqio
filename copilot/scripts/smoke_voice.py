"""Live smoke: one whisper to the earpiece, one interjection to the public device.

PINOQIO_ENV_FILE=<.env> uv run python scripts/smoke_voice.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pinoqio.voice import Voice  # noqa: E402


async def main() -> None:
    v = Voice()
    for label, task in (
        ("whisper", v.whisper("Price changed. Ask why.")),
        ("interject", None),
    ):
        if label == "interject":
            task = v.interject("Sorry to jump in. Earlier you said forty thousand, now forty-eight. Which one is it?")
        await task
        print(f"{label}: done")


asyncio.run(main())
