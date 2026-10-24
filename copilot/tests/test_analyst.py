import pytest

from pinoqio.analyst import analyze, merge_ledger
from pinoqio.events import LedgerItem, Utterance
from pinoqio.gemma import GemmaError, parse_json

HIST = (
    Utterance(1, "them", "The unit price is 40k euros.", 42.0, 45.0),
    Utterance(2, "me", "Great, and delivery?", 46.0, 48.0),
    Utterance(3, "them", "Well, it will be 48k euros per unit.", 50.0, 54.0),
)


def fake(data):
    async def ask(prompt, system):
        if isinstance(data, Exception):
            raise data
        return data

    return ask


GOOD = {
    "contradiction": {"now_quote": "48k euros", "then_quote": "40K  euros", "then_utterance_id": 1, "confidence": 0.9},
    "evasion": {"score": 0.2, "why": "mostly answers"},
    "number_drift": {"item": "unit price", "then_value": "40k", "now_value": "48k", "then_utterance_id": 1},
    "hedging": {"score": 0.5, "phrases": ["Well"]},
    "ledger_updates": [{"who": "them", "item": "unit price", "value": "48k"}, {"who": "x", "item": "a", "value": "b"}],
    "ask_next": "Why did the price change?",
}


async def test_valid_analysis():
    a = await analyze(HIST, (), fake(GOOD))
    assert a.utterance_id == 3
    assert a.contradiction and a.contradiction.then_utterance_id == 1 and a.contradiction.confidence == 0.9
    assert a.number_drift and a.number_drift.then_t == 42.0
    assert a.hedge_phrases == ("Well",) and a.ask_next == "Why did the price change?"
    assert [i.item for i in a.ledger_updates] == ["unit price"]  # bad 'who' dropped
    assert a.ledger_updates[0].utterance_id == 3


@pytest.mark.parametrize(
    "bad",
    [
        {"now_quote": "invented words", "then_quote": "40k euros", "then_utterance_id": 1, "confidence": 1},
        {"now_quote": "48k euros", "then_quote": "not said", "then_utterance_id": 1, "confidence": 1},
        {"now_quote": "48k euros", "then_quote": "40k euros", "then_utterance_id": 2, "confidence": 1},  # wrong speaker
        {"now_quote": "48k euros", "then_quote": "40k euros", "then_utterance_id": 3, "confidence": 1},  # not earlier
        {"now_quote": "48k euros", "then_quote": "40k euros", "then_utterance_id": 99, "confidence": 1},
        "garbage",
    ],
)
async def test_unverifiable_contradiction_dropped(bad):
    a = await analyze(HIST, (), fake({**GOOD, "contradiction": bad}))
    assert a.contradiction is None


async def test_wrong_types_degrade_to_neutral():
    a = await analyze(HIST, (), fake({"evasion": "x", "hedging": [], "ledger_updates": "no", "contradiction": 5}))
    assert a.evasion == 0 and a.hedging == 0 and a.ledger_updates == () and a.ask_next is None


async def test_scores_clamped():
    a = await analyze(HIST, (), fake({"evasion": {"score": 7}, "hedging": {"score": -1}}))
    assert a.evasion == 1.0 and a.hedging == 0.0


async def test_gemma_error_propagates():
    with pytest.raises(GemmaError):
        await analyze(HIST, (), fake(GemmaError("boom")))


def test_parse_json_variants():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Here: {"a": 1} done') == {"a": 1}
    assert parse_json('[{"a": 1}]') == {"a": 1}  # one-item list is unwrapped
    for bad in ("not json", "[1]", "{broken"):
        with pytest.raises(GemmaError):
            parse_json(bad)


def test_merge_ledger_replaces_same_item():
    old = (LedgerItem("them", "Unit price", "40k", 1), LedgerItem("them", "delivery", "March", 1))
    new = merge_ledger(old, (LedgerItem("them", "unit price", "48k", 3),))
    assert [(i.item, i.value) for i in new] == [("delivery", "March"), ("unit price", "48k")]
    assert old[0].value == "40k"
