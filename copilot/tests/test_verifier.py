import pytest

from pinoqio.analyst import Analysis, NumberDrift
from pinoqio.events import Contradiction, Utterance
from pinoqio.verifier import UNVERIFIED_CAP, claim_from, refine

HIST = (
    Utterance(1, "them", "Hello there. The delivery is mid-March. Price is fine.", 10.0, 14.0),
    Utterance(2, "me", "Delivery?", 15.0, 16.0),
    Utterance(3, "them", "Actually it is the end of April.", 70.0, 73.0),
)
DRIFT = NumberDrift("delivery date", "mid-March", "end of April", 10.0, 1)
CONTRA = Contradiction("end of April", "mid-March", 1, 0.9)


def mock(data):
    async def ask(prompt, system):
        if isinstance(data, Exception):
            raise data
        return data

    return ask


def test_claim_from_drift_uses_verbatim_sentences():
    c = claim_from(Analysis(utterance_id=3, number_drift=DRIFT), HIST)
    assert c.then_quote == "The delivery is mid-March." and c.then_quote in HIST[0].text
    assert c.now_quote == HIST[2].text and c.then_id == 1


def test_claim_from_contradiction_preferred_and_none_when_nothing_flagged():
    c = claim_from(Analysis(contradiction=CONTRA, number_drift=DRIFT), HIST)
    assert c.then_quote == "mid-March" and c.item == "delivery date"
    assert claim_from(Analysis(), HIST) is None
    assert claim_from(Analysis(number_drift=NumberDrift("x", "a", "b")), HIST) is None  # no then_id


async def test_confirmed_drift_becomes_contradiction():
    a, v = await refine(Analysis(utterance_id=3, number_drift=DRIFT), HIST, (), mock({"is_contradiction": True, "confidence": 0.95, "reason": "r"}))
    assert a.contradiction == Contradiction(HIST[2].text, "The delivery is mid-March.", 1, 0.95)
    assert a.number_drift == DRIFT and v.is_contradiction


async def test_verifier_confidence_replaces_gemma_confidence():
    a, _ = await refine(Analysis(contradiction=CONTRA), HIST, (), mock({"is_contradiction": True, "confidence": 0.7, "reason": ""}))
    assert a.contradiction.confidence == 0.7


async def test_rejected_contradiction_dropped_drift_kept():
    a, v = await refine(Analysis(contradiction=CONTRA, number_drift=DRIFT), HIST, (), mock({"is_contradiction": False, "confidence": 0.9, "reason": "compatible"}))
    assert a.contradiction is None and a.number_drift == DRIFT and not v.is_contradiction


@pytest.mark.parametrize("bad", [RuntimeError("down"), {"confidence": 0.9}, {"is_contradiction": "yes", "confidence": 1}, {"is_contradiction": True}])
async def test_failure_keeps_gemma_but_caps_confidence(bad):
    a, v = await refine(Analysis(contradiction=Contradiction("n", "t", 1, 0.99)), HIST, (), mock(bad))
    assert v is None and a.contradiction.confidence == UNVERIFIED_CAP


async def test_no_claim_means_no_call():
    a, v = await refine(Analysis(), HIST, (), mock(RuntimeError("must not be called")))
    assert a == Analysis() and v is None
