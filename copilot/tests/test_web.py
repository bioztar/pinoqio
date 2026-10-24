import json

from fastapi.testclient import TestClient

from pinoqio import record, web


def _replay_dir(tmp_path):
    lines = [{"t": 0.0, "type": "utterance", "id": 1, "speaker": "them", "text": "hi"},
             {"t": 0.01, "type": "verdict", "utterance_id": 1, "probability": 0.5}]
    (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(l) for l in lines))
    (tmp_path / "call.mp3").write_bytes(b"ID3fake")
    return tmp_path


def test_index_has_bar_and_hides_live_without_passcode(tmp_path):
    client = TestClient(web.create_web_app(_replay_dir(tmp_path)))
    html = client.get("/").text
    assert "Play demo" in html and "github.com/bioztar/pinoqio" in html
    assert "window.PINOQIO_LIVE = false" in html
    assert "window.PINOQIO_LIVE = true" in TestClient(web.create_web_app(_replay_dir(tmp_path), "pw")).get("/").text


def test_each_connection_gets_its_own_full_replay(tmp_path):
    client = TestClient(web.create_web_app(_replay_dir(tmp_path)))
    assert client.get("/demo/call.mp3").content == b"ID3fake"
    for _ in range(2):
        with client.websocket_connect("/demo") as ws:
            ws.send_text("start")
            kinds = [ws.receive_json()["type"] for _ in range(3)]
        assert kinds == ["utterance", "verdict", "end"]


def test_shipped_demo_assets_load():
    events = record.load(web.REPLAY_DIR / "events.jsonl")
    assert {e["type"] for e in events} == {"utterance", "verdict", "summary"}
    assert events[-1]["type"] == "summary"  # post-call summary closes the recording
    assert [e["t"] for e in events] == sorted(e["t"] for e in events)
    assert (web.REPLAY_DIR / "call.mp3").stat().st_size > 10_000
