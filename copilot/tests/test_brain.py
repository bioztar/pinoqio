import asyncio

from pinoqio import brain
from pinoqio.brain import verdicts
from pinoqio.events import Utterance, Verdict
from pinoqio.gemma import GemmaError


async def stream(items):
    for i in items:
        yield i


UTTS = [
    Utterance(1, "them", "Price is 40k.", 0, 2),
    Utterance(2, "me", "Ok.", 3, 4),
    Utterance(3, "them", "Now 48k.", 5, 7, {"pitch_mean_hz_z": 2.0}),
]


def raising(exc):
    async def ask(prompt, system):
        raise exc

    return ask


async def collect(ask, fallback=None, verify_ask=None):
    fallback = fallback or raising(RuntimeError("no fallback"))
    return [x async for x in verdicts(stream(UTTS), ask, fallback, verify_ask)]


def models(v):
    return [c.label for c in v.chips if c.kind == "model"]


async def test_passthrough_and_verdict_per_them_utterance():
    async def ask(prompt, system):
        return {"ledger_updates": [{"who": "them", "item": "price", "value": "40k"}]}

    out = await collect(ask)
    assert [type(x) for x in out] == [Utterance, Verdict, Utterance, Utterance, Verdict]
    assert out[1].utterance_id == 1 and out[4].utterance_id == 3
    assert len(out[1].ledger) == 1 and len(out[4].ledger) == 1  # same item, replaced
    assert models(out[1]) == ["Gemma 4"]  # nothing flagged, verifier did not run


async def test_both_models_down_gives_vocal_only_verdict():
    out = await collect(raising(GemmaError("down")))
    v = out[-1]
    assert isinstance(v, Verdict) and v.verbal < 0.15 and v.vocal > 0.12 and v.ledger == ()
    assert models(v) == []


async def test_gemma_error_falls_back_to_nebius():
    async def fb(prompt, system):
        return {"ledger_updates": [{"who": "them", "item": "price", "value": "40k"}]}

    out = await collect(raising(GemmaError("down")), fb)
    assert len(out[1].ledger) == 1
    assert "fallback" in models(out[1])[0]


async def test_gemma_over_budget_falls_back(monkeypatch):
    monkeypatch.setattr(brain, "GEMMA_BUDGET_S", 0.05)

    async def slow(prompt, system):
        await asyncio.sleep(1)
        return {}

    async def fb(prompt, system):
        return {"ask_next": "from fallback"}

    out = await collect(slow, fb)
    assert out[1].ask_next == "from fallback"


async def test_flagged_drift_is_verified_and_upgraded():
    async def ask(prompt, system):
        if "40k" in prompt and "Now 48k" in prompt:
            return {"number_drift": {"item": "price", "then_value": "40k", "now_value": "48k", "then_utterance_id": 1}}
        return {}

    async def verifier(prompt, system):
        return {"is_contradiction": True, "confidence": 0.93, "reason": "same item"}

    out = await collect(ask, verify_ask=verifier)
    first, last = out[1], out[4]
    assert first.contradiction is None
    assert last.contradiction and last.contradiction.confidence == 0.93 and last.contradiction.then_utterance_id == 1
    assert "verified by" in models(last)[1]


async def test_verifier_failure_caps_gemma_contradiction():
    async def ask(prompt, system):
        if "Now 48k" in prompt:
            return {"contradiction": {"now_quote": "48k", "then_quote": "40k", "then_utterance_id": 1, "confidence": 0.99}}
        return {}

    out = await collect(ask, verify_ask=raising(RuntimeError("down")))
    assert out[4].contradiction.confidence == 0.8
    assert models(out[4]) == ["Gemma 4"]
