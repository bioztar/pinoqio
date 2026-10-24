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


async def collect(ask):
    return [x async for x in verdicts(stream(UTTS), ask)]


async def test_passthrough_and_verdict_per_them_utterance():
    async def ask(prompt, system):
        return {"ledger_updates": [{"who": "them", "item": "price", "value": "40k"}]}

    out = await collect(ask)
    assert [type(x) for x in out] == [Utterance, Verdict, Utterance, Utterance, Verdict]
    assert out[1].utterance_id == 1 and out[4].utterance_id == 3
    assert len(out[1].ledger) == 1 and len(out[4].ledger) == 1  # same item, replaced


async def test_gemma_failure_gives_vocal_only_verdict():
    async def ask(prompt, system):
        raise GemmaError("down")

    out = await collect(ask)
    v = out[-1]
    assert isinstance(v, Verdict) and v.verbal < 0.15 and v.vocal > 0.12 and v.ledger == ()
