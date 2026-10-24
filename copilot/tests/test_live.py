import asyncio

import numpy as np
from fastapi.testclient import TestClient

from pinoqio import ears, web
from pinoqio.events import Utterance
from tests.test_web import _replay_dir


async def fake_pipeline(them, me):
    async for c in them:
        yield Utterance(1, "them", f"them:{len(c)}", 0.0, 1.0, {})
    async for c in me:
        yield Utterance(2, "me", f"me:{len(c)}", 0.0, 1.0, {})


def pcm(channel: int, n: int) -> bytes:
    return bytes([channel]) + np.zeros(n, "<i2").tobytes()


def client(tmp_path, passcode="pw", pipeline=fake_pipeline):
    return TestClient(web.create_web_app(_replay_dir(tmp_path), passcode, pipeline))


def test_no_live_route_without_passcode(tmp_path):
    c = TestClient(web.create_web_app(_replay_dir(tmp_path)))
    try:
        with c.websocket_connect("/live"):
            raise AssertionError("route should not exist")
    except Exception as e:
        assert "AssertionError" not in type(e).__name__


def test_wrong_passcode_rejected(tmp_path):
    with client(tmp_path).websocket_connect("/live") as ws:
        ws.send_json({"passcode": "nope"})
        assert ws.receive_json() == {"type": "error", "message": "Wrong passcode."}


def test_channels_route_to_them_and_me_and_stop_ends(tmp_path):
    with client(tmp_path).websocket_connect("/live") as ws:
        ws.send_json({"passcode": "pw"})
        assert ws.receive_json() == {"type": "ready"}
        ws.send_bytes(pcm(1, 1600))
        ws.send_bytes(pcm(0, 800))
        ws.send_text("stop")
        got = [ws.receive_json() for _ in range(3)]
    assert [(m["speaker"], m["text"]) for m in got[:2]] == [("them", "them:1600"), ("me", "me:800")]
    assert got[2] == {"type": "end"}


def test_one_session_at_a_time_and_released_after(tmp_path):
    c = client(tmp_path)
    with c.websocket_connect("/live") as first:
        first.send_json({"passcode": "pw"})
        assert first.receive_json()["type"] == "ready"
        with c.websocket_connect("/live") as second:
            second.send_json({"passcode": "pw"})
            assert "Another live session" in second.receive_json()["message"]
        first.send_text("stop")
        assert first.receive_json() == {"type": "end"}
    with c.websocket_connect("/live") as again:
        again.send_json({"passcode": "pw"})
        assert again.receive_json() == {"type": "ready"}


def test_cap_ends_session(tmp_path):
    from fastapi import FastAPI, WebSocket

    from pinoqio import live

    async def slow(them, me):
        await asyncio.sleep(5)
        yield  # pragma: no cover

    app, state = FastAPI(), live.LiveState()

    @app.websocket("/live")
    async def capped(sock: WebSocket):
        await live.run_session(sock, "pw", state, slow, cap_seconds=0.2)

    with TestClient(app).websocket_connect("/live") as ws:
        ws.send_json({"passcode": "pw"})
        assert ws.receive_json() == {"type": "ready"}
        assert ws.receive_json()["type"] == "end"


async def test_ears_stream_source_validates():
    try:
        async for _ in ears.utterances("stream"):
            pass
    except ValueError as e:
        assert "streams" in str(e)
    else:
        raise AssertionError("expected ValueError")
