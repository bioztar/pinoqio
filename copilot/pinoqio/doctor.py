"""Stage preflight: uv run python -m pinoqio.doctor. Green/red checklist in under 20 s. Key values are never printed."""
import asyncio
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import numpy as np

from pinoqio import audio, config

SIGNAL_RMS = 0.002  # int16 full scale = 1.0; room tone is ~0.0005, a speaking voice ~0.02+
LISTEN_S = 3.0
CHECK_TIMEOUT_S = 12.0
MIN_DISK_GB = 2.0
MIN_BATTERY_PCT = 40
KEYS = ("GEMINI_API_KEY", "ELEVENLABS_API_KEY", "NEBIUS_API_KEY")
MULTI_OUTPUT_HINT = "Teams speaker must be the Multi-Output device"

OK, FAIL, WARN = "ok", "fail", "warn"
_MARK = {OK: "\033[32m✔\033[0m", FAIL: "\033[31m✘\033[0m", WARN: "\033[33m!\033[0m"}


@dataclass(frozen=True)
class Result:
    name: str
    status: str
    detail: str = ""


# ---- pure logic (unit tested) ----

def rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    x = samples.astype(np.float64)
    if samples.dtype.kind == "i":
        x = x / 32768.0
    return float(np.sqrt(np.mean(x * x)))


def signal_result(level: float) -> Result:
    detail = f"rms {level:.4f} over {LISTEN_S:.0f} s"
    if level >= SIGNAL_RMS:
        return Result("BlackHole receiving signal", OK, detail)
    return Result("BlackHole receiving signal", FAIL, f"silent ({detail}). {MULTI_OUTPUT_HINT}")


def device_result(label: str, needle: str, names: list[str]) -> Result:
    found = next((n for n in names if needle.lower() in n.lower()), None)
    if found:
        return Result(label, OK, found)
    return Result(label, FAIL, f"{needle!r} not found; have: {', '.join(names) or 'none'}")


def keys_result(env: dict[str, str]) -> Result:
    missing = [k for k in KEYS if not env.get(k)]
    if missing:
        return Result("API keys", FAIL, "missing " + ", ".join(missing))
    return Result("API keys", OK, ", ".join(KEYS))


def latency_result(name: str, seconds: float, limit: float) -> Result:
    detail = f"{seconds:.1f} s"
    return Result(name, OK if seconds <= limit else WARN, detail if seconds <= limit else f"{detail} (slow, > {limit:.0f} s)")


def parse_batt(text: str) -> tuple[int | None, bool | None]:
    """(percent, on_ac) from `pmset -g batt`; None where the text doesn't say (e.g. desktop Mac)."""
    pct = re.search(r"(\d+)%", text)
    ac = re.search(r"Now drawing from '(AC|Battery) Power'", text)
    return (int(pct.group(1)) if pct else None, ac.group(1) == "AC" if ac else None)


def power_result(text: str) -> list[Result]:
    pct, ac = parse_batt(text)
    batt = Result("Battery", OK if pct is None or pct >= MIN_BATTERY_PCT else FAIL, f"{pct}%" if pct is not None else "no battery")
    adapter = Result("Power adapter", OK if ac else FAIL, "connected" if ac else "on battery, plug in the charger")
    return [batt, adapter]


def disk_result(free_bytes: int) -> Result:
    gb = free_bytes / 1e9
    return Result("Free disk", OK if gb >= MIN_DISK_GB else FAIL, f"{gb:.0f} GB free")


# ---- checks that touch the machine or network ----

def check_devices() -> list[Result]:
    import sounddevice as sd
    devices = sd.query_devices()
    ins = [d["name"] for d in devices if d["max_input_channels"] > 0]
    outs = [d["name"] for d in devices if d["max_output_channels"] > 0]
    from pinoqio.voice import DEFAULT_PUBLIC_DEVICE, DEFAULT_WHISPER_DEVICE
    them, me = audio.device_names()
    return [
        device_result("BlackHole 2ch (input)", them, ins),
        device_result("Microphone", me, ins),
        device_result("Shokz (whisper out)", os.environ.get("PINOQIO_WHISPER_DEVICE", DEFAULT_WHISPER_DEVICE), outs),
        device_result("MacBook speakers", os.environ.get("PINOQIO_PUBLIC_DEVICE", DEFAULT_PUBLIC_DEVICE), outs),
    ]


def check_signal() -> Result:
    import sounddevice as sd
    try:
        idx, _ = audio.find_device(audio.device_names()[0])
    except audio.DeviceNotFound as e:
        return Result("BlackHole receiving signal", FAIL, str(e))
    block = sd.rec(int(LISTEN_S * audio.SR), samplerate=audio.SR, channels=1, dtype="int16", device=idx)
    sd.wait()
    return signal_result(rms(block))


def check_keys() -> Result:
    config._load()
    return keys_result(dict(os.environ))


def check_system() -> list[Result]:
    batt = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5).stdout
    return [
        *power_result(batt),
        disk_result(shutil.disk_usage("/").free),
        Result("Do Not Disturb", WARN, "check by hand: Focus on, so no notifications pop over the demo"),
    ]


async def _timed(name: str, coro: Awaitable, limit: float) -> Result:
    start = time.monotonic()
    try:
        await asyncio.wait_for(coro, CHECK_TIMEOUT_S)
    except Exception as e:  # any failure is a red line, not a crash
        return Result(name, FAIL, f"{type(e).__name__}: {e}"[:140])
    return latency_result(name, time.monotonic() - start, limit)


PING = "Reply with this JSON object only: {\"ok\": true}"


async def ping_gemma() -> None:
    from pinoqio import gemma
    await gemma.ask_json(PING)


async def ping_nebius() -> None:
    from pinoqio import nebius
    await nebius.ask_json(PING)


async def ping_scribe() -> None:
    import websockets
    from pinoqio import stt
    async with websockets.connect(stt._url(), additional_headers={"xi-api-key": stt.api_key()}, open_timeout=8):
        pass  # handshake accepted = key, plan and model are fine


async def ping_tts() -> None:
    from pinoqio import voice
    await asyncio.to_thread(voice.synth_pcm, "ok")


NETWORK: tuple[tuple[str, Callable[[], Awaitable], float], ...] = (
    ("Gemma 26B round-trip", ping_gemma, 5.0),
    ("Nebius verifier round-trip", ping_nebius, 3.0),
    ("ElevenLabs Scribe websocket", ping_scribe, 3.0),
    ("ElevenLabs TTS", ping_tts, 4.0),
)


async def prewarm() -> list[Result]:
    """Open the model/Scribe/TTS connections so the first live call isn't cold. Used by `app --demo-safe`."""
    return await asyncio.gather(*(_timed(n, fn(), lim) for n, fn, lim in NETWORK))


async def run_all() -> list[Result]:
    network = asyncio.create_task(prewarm())  # overlaps the 3 s BlackHole listen
    local = await asyncio.gather(
        asyncio.to_thread(check_devices), asyncio.to_thread(check_signal),
        asyncio.to_thread(check_keys), asyncio.to_thread(check_system),
    )
    return [*local[0], local[1], local[2], *await network, *local[3]]


def render(results: list[Result]) -> str:
    return "\n".join(f"{_MARK[r.status]} {r.name}" + (f"  {r.detail}" if r.detail else "") for r in results)


def main() -> int:
    start = time.monotonic()
    results = asyncio.run(run_all())
    print(render(results))
    bad = sum(r.status == FAIL for r in results)
    print(f"\n{'READY' if not bad else f'{bad} RED'}  ({time.monotonic() - start:.1f} s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
