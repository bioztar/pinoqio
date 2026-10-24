"""Pinoqio's voice: ElevenLabs TTS to named output devices, plus the speak/stay-quiet policy.

whisper(text)   -> private earpiece (PINOQIO_WHISPER_DEVICE)
interject(text) -> into the call via speaker/BlackHole (PINOQIO_PUBLIC_DEVICE)
decide(...)     -> pure policy, no audio, unit-tested.
"""
import asyncio
import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path

import httpx
import numpy as np
import sounddevice as sd
from dotenv import load_dotenv

from pinoqio.events import Verdict

log = logging.getLogger("pinoqio.voice")

TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
TTS_MODEL = "eleven_flash_v2_5"  # low-latency
PLAY_RATE = 24000
DEFAULT_VOICE = "pNInz6obpgDQGcFmaJgB"  # Adam, premade
DEFAULT_WHISPER_DEVICE = "OpenRun Pro 2 by Shokz"
DEFAULT_PUBLIC_DEVICE = "MacBook Air Speakers"

WHISPER_MIN_PROB = 0.6
WHISPER_GAP_S = 8.0
INTERJECT_MIN_CONF = 0.85
MAX_CUE_WORDS = 8
MAX_QUOTE_WORDS = 10

_CUES = {
    "contradiction": "Contradiction. Ask which is true.",
    "number_drift": "Number changed. Ask why.",
    "evasion": "Dodged. Repeat the question.",
    "hedging": "Hedging. Press for specifics.",
}
_DEFAULT_CUE = "Possible bluff. Probe that."


# ---------- policy (pure) ----------

@dataclass(frozen=True)
class Action:
    kind: str  # "whisper" | "interject"
    text: str


@dataclass(frozen=True)
class PolicyState:
    last_whisper_t: float | None = None
    interjected: bool = False
    said: frozenset[str] = frozenset()  # public mode: inconsistencies already called out


def _words(text: str, n: int) -> str:
    w = text.strip().rstrip(".,;:!?").split()  # a trailing "." before the ellipsis/comma sounds broken aloud
    return " ".join(w[:n]) + ("..." if len(w) > n else "")


def cue_for(v: Verdict) -> str:
    """Whisper text, at most MAX_CUE_WORDS words."""
    if v.ask_next and len(v.ask_next.split()) <= MAX_CUE_WORDS:
        return v.ask_next
    if v.chips:
        top = max(v.chips, key=lambda c: c.weight)
        return _CUES.get(top.kind, _DEFAULT_CUE)
    return _DEFAULT_CUE


def interjection_for(v: Verdict) -> str:
    c = v.contradiction
    return (
        f"Sorry to jump in. Earlier you said {_words(c.then_quote, MAX_QUOTE_WORDS)}, "
        f"now {_words(c.now_quote, MAX_QUOTE_WORDS)}. Which one is it?"
    )


def decide(state: PolicyState, v: Verdict, now: float) -> tuple[PolicyState, Action | None]:
    """Pick at most one action for this verdict. `now` is any monotonic seconds clock."""
    c = v.contradiction
    if c is not None and c.confidence >= INTERJECT_MIN_CONF and not state.interjected:
        return replace(state, interjected=True, last_whisper_t=now), Action("interject", interjection_for(v))
    if v.probability >= WHISPER_MIN_PROB and (
        state.last_whisper_t is None or now - state.last_whisper_t >= WHISPER_GAP_S
    ):
        return replace(state, last_whisper_t=now), Action("whisper", cue_for(v))
    return state, None


# Voice modes (PINOQIO_VOICE_MODE, or `pinoqio.app --voice`):
#   public  = every inconsistency is said out loud into the call (demo)
#   whisper = earpiece cues + one public interjection per call (default, the original policy)
#   private = silent; the window shows the lie % and evidence only
VOICE_MODES = ("public", "whisper", "private")
PUBLIC_MIN_CONF = 0.6
INCONSISTENCY_KINDS = ("contradiction", "number_drift")


def voice_mode() -> str:
    mode = os.environ.get("PINOQIO_VOICE_MODE", "whisper")
    return mode if mode in VOICE_MODES else "whisper"


def callout_for(v: Verdict) -> tuple[str, str] | None:
    """(dedupe key, line to say) for an inconsistency in this verdict, else None.

    Keyed by topic (the drift chip's "Delivery date: ..." prefix) so a contradiction and
    the matching number drift on a later line are called out once, not twice.
    """
    drift = [ch for ch in v.chips if ch.kind == "number_drift"]
    topic = max(drift, key=lambda ch: ch.weight).label.split(":")[0].strip().lower() if drift else None
    c = v.contradiction
    if c is not None and c.confidence >= PUBLIC_MIN_CONF:
        return f"t:{topic}" if topic else f"c:{c.then_utterance_id}", interjection_for(v)
    if drift:
        label = _words(max(drift, key=lambda ch: ch.weight).label, 16)
        return f"t:{topic}", f"Sorry to jump in. {label}. Which one is it?"
    return None


def decide_public(state: PolicyState, v: Verdict) -> tuple[PolicyState, Action | None]:
    """Public mode: say each distinct inconsistency out loud once."""
    hit = callout_for(v)
    if hit is None or hit[0] in state.said:
        return state, None
    return replace(state, said=state.said | {hit[0]}), Action("interject", hit[1])


# ---------- TTS ----------

def load_api_key() -> str:
    """Same contract as config.py (brain lane): load .env, require the key by name."""
    root = Path(__file__).resolve().parents[2]
    load_dotenv(os.environ.get("PINOQIO_ENV_FILE", root / ".env"))
    try:
        return os.environ["ELEVENLABS_API_KEY"]
    except KeyError:
        raise RuntimeError("ELEVENLABS_API_KEY is not set (put it in .env or PINOQIO_ENV_FILE)") from None


def synth_pcm(text: str, voice_id: str = DEFAULT_VOICE, rate: int = PLAY_RATE,
              client: httpx.Client | None = None) -> np.ndarray:
    """Text -> mono int16 PCM at `rate` Hz via ElevenLabs (pcm_<rate>)."""
    key = load_api_key()
    body = {"text": text, "model_id": TTS_MODEL}
    url = TTS_URL.format(voice_id=voice_id)
    http = client or httpx.Client(timeout=30)
    try:
        r = http.post(url, params={"output_format": f"pcm_{rate}"},
                      headers={"xi-api-key": key}, json=body)
        r.raise_for_status()
    finally:
        if client is None:
            http.close()
    return np.frombuffer(r.content, dtype="<i2")


def resolve_device(name: str) -> int | None:
    """Output device index whose name contains `name` (case-insensitive); None = system default."""
    needle = name.lower()
    for i, d in enumerate(sd.query_devices()):
        if d["max_output_channels"] > 0 and needle in d["name"].lower():
            return i
    log.warning("output device %r not found, using system default", name)
    return None


def play_pcm(pcm: np.ndarray, device: int | None, rate: int = PLAY_RATE) -> None:
    sd.play(pcm, rate, device=device)
    sd.wait()


class Voice:
    """Speaks whisper/interject without ever overlapping two clips."""

    def __init__(self, voice_id: str | None = None):
        self._voice_id = voice_id or os.environ.get("PINOQIO_VOICE_ID", DEFAULT_VOICE)
        self._lock = asyncio.Lock()
        self._state = PolicyState()

    async def _speak(self, text: str, device_name: str) -> None:
        async with self._lock:
            try:
                loop = asyncio.get_running_loop()
                pcm = await loop.run_in_executor(None, synth_pcm, text, self._voice_id)
                device = resolve_device(device_name)
                log.info("voice: playing %r on %r (device %s)", text, device_name, device)
                await loop.run_in_executor(None, play_pcm, pcm, device)
            except Exception:  # never crash the live pipeline
                log.exception("voice: speak failed, skipping %r", text)

    def whisper(self, text: str) -> "asyncio.Task | None":
        """Private cue. Dropped (not queued) if a clip is already playing: stale advice is noise."""
        if self._lock.locked():
            return None
        dev = os.environ.get("PINOQIO_WHISPER_DEVICE", DEFAULT_WHISPER_DEVICE)
        return asyncio.create_task(self._speak(text, dev))

    def interject(self, text: str, force: bool = False) -> "asyncio.Task | None":
        """Public line into the call. Once per session unless force=True."""
        if self._state.interjected and not force:
            return None
        self._state = replace(self._state, interjected=True)
        dev = os.environ.get("PINOQIO_PUBLIC_DEVICE", DEFAULT_PUBLIC_DEVICE)
        return asyncio.create_task(self._speak(text, dev))

    def on_verdict(self, v: Verdict, now: float | None = None) -> Action | None:
        """Apply the policy to a verdict and speak the result. Returns the action taken."""
        mode = voice_mode()
        if mode == "private":
            return None
        if mode == "public":
            self._state, action = decide_public(self._state, v)
            if action is not None:
                dev = os.environ.get("PINOQIO_PUBLIC_DEVICE", DEFAULT_PUBLIC_DEVICE)
                asyncio.create_task(self._speak(action.text, dev))  # the lock queues clips in order
            return action
        t = asyncio.get_running_loop().time() if now is None else now
        new_state, action = decide(self._state, v, t)
        if action is None:
            return None
        if action.kind == "interject":
            self._state = new_state
            asyncio.create_task(self._speak(action.text, os.environ.get("PINOQIO_PUBLIC_DEVICE", DEFAULT_PUBLIC_DEVICE)))
        else:
            if self._lock.locked():
                return None
            self._state = new_state
            self.whisper(action.text)
        return action


# Module-level hooks used by app.py (auto policy) and server.py (the "Say it" button).
# ponytail: one process-wide Voice; per-session state resets only on restart.
_voice: Voice | None = None


def _shared() -> Voice:
    global _voice
    if _voice is None:
        _voice = Voice()
    return _voice


def on_verdict(v: Verdict) -> Action | None:
    return _shared().on_verdict(v)


def interject(text: str, force: bool = True) -> "asyncio.Task | None":
    """The "Say it" button: an explicit press always speaks (and counts as the session's interjection)."""
    return _shared().interject(text, force)
