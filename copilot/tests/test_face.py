from fastapi.testclient import TestClient

from pinoqio import fake
from pinoqio.events import Chip, Contradiction, LedgerItem, Utterance, Verdict
from pinoqio.server import create_app, to_json


def test_utterance_json():
    u = Utterance(1, "them", "hi", 0.0, 1.5, {"pitch_mean_hz": 120.0})
    assert to_json(u) == {"type": "utterance", "id": 1, "speaker": "them", "text": "hi",
                          "t_start": 0.0, "t_end": 1.5, "prosody": {"pitch_mean_hz": 120.0}}


def test_verdict_json_nested():
    v = Verdict(3, 0.8, 0.9, 0.5,
                chips=(Chip("contradiction", "price drift", 0.5, "48k"),),
                contradiction=Contradiction("48k", "40k", 2, 0.9),
                ledger=(LedgerItem("them", "unit price", "48k", 3),), ask_next="why?")
    j = to_json(v)
    assert j["type"] == "verdict"
    assert j["chips"][0]["kind"] == "contradiction"
    assert j["contradiction"]["then_utterance_id"] == 2
    assert j["ledger"][0]["value"] == "48k"
    assert to_json(Verdict(1, 0.1, 0.1, 0.1))["contradiction"] is None


async def test_fake_emits_both_types_with_contradictions():
    out = [e async for e in fake.events(speed=10_000)]
    assert {type(e) for e in out} == {Utterance, Verdict}
    assert sum(1 for e in out if isinstance(e, Verdict) and e.contradiction) == 2


def test_index_interject_and_ws_replay():
    sent: list[str] = []

    async def source(_):
        async for e in fake.events(speed=10_000):
            yield e

    with TestClient(create_app(source, interject=sent.append)) as client:
        assert "Pinoqio" in client.get("/").text
        assert client.post("/interject", json={"text": "hello"}).json() == {"ok": True}
        assert sent == ["hello"]
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json()["type"] in {"utterance", "verdict"}
