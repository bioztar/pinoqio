import dataclasses

from fastapi.testclient import TestClient

from pinoqio import server, summary
from pinoqio.app import with_summary
from pinoqio.events import Contradiction, LedgerItem, Utterance, Verdict

C = Contradiction("48k", "40k", 1, 0.95)
EVENTS = (
    Utterance(1, "them", "The price is 40k euros.", 5.0, 8.0),
    Utterance(2, "me", "What is the defect rate?", 9.0, 11.0),
    Utterance(3, "them", "Now it is 48k euros. Things change.", 20.0, 24.0),
    Verdict(3, 0.95, 0.9, 0.1, contradiction=C, ledger=(LedgerItem("them", "price", "48k", 3),)),
)

GOOD = {
    "commitments": [
        {"who": "them", "item": "price", "value": "48k", "changed": True, "was": "40k"},
        {"who": "x", "item": "bad", "value": "who"},
        {"who": "me", "item": "", "value": "empty item"},
    ],
    "open_questions": ["What is the defect rate?", 5, " "],
    "red_flags": [
        {"text": "Price rose 20%", "quote": "Now it is 48k euros"},
        {"text": "Invented quote", "quote": "never said this"},
        {"text": ""},
    ],
    "next_email": "Please confirm 40k in writing.",
}


def mock(data):
    async def ask(prompt, system):
        if isinstance(data, Exception):
            raise data
        return data

    return ask


def test_digest_same_from_objects_and_json_dicts():
    from_objs = summary.digest(EVENTS)
    from_json = summary.digest([server.to_json(e) for e in EVENTS])
    assert from_objs == from_json
    assert len(from_objs.lines) == 3 and from_objs.ledger[0]["value"] == "48k"
    assert from_objs.contradictions == (("40k", "48k"),)


async def test_summarize_validates_model_output():
    s = await summary.summarize(EVENTS, mock(GOOD))
    assert [(c.who, c.item, c.changed, c.was) for c in s.commitments] == [("them", "price", True, "40k")]
    assert s.open_questions == ("What is the defect rate?",)
    assert [(f.text, f.quote) for f in s.red_flags] == [("Price rose 20%", "Now it is 48k euros"), ("Invented quote", None)]
    assert s.next_email.startswith("Please confirm")


async def test_failure_or_garbage_degrades_not_raises():
    for bad in (RuntimeError("down"), {"commitments": "no", "red_flags": 3}):
        s = await summary.summarize(EVENTS, mock(bad))
        assert s is not None
    s = await summary.summarize(EVENTS, mock(RuntimeError("down")))
    assert s.model == "offline" and s.commitments[0].value == "48k" and "40k" in s.red_flags[0].text


async def test_no_counterparty_speech_gives_none():
    assert await summary.summarize((EVENTS[1],), mock(GOOD)) is None


def test_summary_event_json():
    j = server.to_json(summary.Summary(next_email="x", model="m"))
    assert j["type"] == "summary" and j["commitments"] == () and j["next_email"] == "x"


async def test_with_summary_appends_at_call_end(monkeypatch):
    async def fake(events, ask=None):
        return summary.Summary(next_email="n", model="m")

    monkeypatch.setattr("pinoqio.app.summarize", fake)

    async def src():
        for e in EVENTS:
            yield e

    out = [e async for e in with_summary(src())]
    assert out[:4] == list(EVENTS) and isinstance(out[4], summary.Summary)


def test_summary_endpoint_publishes_to_hub(monkeypatch):
    async def fake(events, ask=None):
        return summary.Summary(next_email="n") if any(m["type"] == "utterance" for m in events) else None

    monkeypatch.setattr(server, "summarize", fake)
    app = server.create_app()
    client = TestClient(app)
    assert client.post("/summary").json() == {"ok": False}
    app.state.hub.publish(EVENTS[0])
    assert client.post("/summary").json() == {"ok": True}
    assert app.state.hub.history[-1]["type"] == "summary"
    assert dataclasses.is_dataclass(summary.Summary())
