import base64
import json

import numpy as np

from pinoqio import stt


class FakeWS:
    """Plays Scribe: commits a transcript after `commit_after` chunks and on commit=True."""

    def __init__(self, commit_after=3):
        self.sent = []
        self.inbox = []
        self.commit_after = commit_after
        self.wakeup = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send(self, raw):
        msg = json.loads(raw)
        self.sent.append(msg)
        n = len(self.sent)
        if msg["commit"] or n == self.commit_after:
            self.inbox.append(json.dumps({"message_type": "committed_transcript", "text": f"seg {n}"}))

    async def recv(self):
        import asyncio
        while not self.inbox:
            await asyncio.sleep(0.01)
        return self.inbox.pop(0)


def loud(n=1600):
    return (np.sin(np.arange(n) / 5) * 8000).astype(np.int16)


async def chunk_source(n):
    for _ in range(n):
        yield loud()


async def test_segments_commit_and_flush(monkeypatch):
    monkeypatch.setattr(stt, "FLUSH_WAIT", 0.2)
    ws = FakeWS(commit_after=3)
    calls = []

    def connect(url, additional_headers):
        calls.append((url, additional_headers))
        return ws

    segs = [s async for s in stt.segments(chunk_source(5), "them", connect=connect, key="k")]
    assert [s.text for s in segs] == ["seg 3", "seg 6"]
    assert "scribe_v2_realtime" in calls[0][0] and "commit_strategy=vad" in calls[0][0]
    assert calls[0][1] == {"xi-api-key": "k"}
    first = ws.sent[0]
    assert first["message_type"] == "input_audio_chunk" and first["sample_rate"] == 16_000
    assert len(base64.b64decode(first["audio_base_64"])) == 3200
    # the buffer is taken when the message arrives, so it holds >= the 3 chunks sent at commit
    assert segs[0].t_start == 0.0 and 0.29 < segs[0].t_end <= 0.5
    assert segs[1].t_start >= segs[0].t_end


async def test_connection_failure_does_not_raise(monkeypatch):
    monkeypatch.setattr(stt, "RECONNECT_DELAY", 0.01)
    monkeypatch.setattr(stt, "FLUSH_WAIT", 0.2)
    attempts = []

    def connect(url, additional_headers):
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("boom")
        return FakeWS()

    segs = [s async for s in stt.segments(chunk_source(2), "me", connect=connect, key="k")]
    assert len(attempts) == 2 and [s.text for s in segs] == ["seg 3"]


def test_missing_key_names_setting(monkeypatch, tmp_path):
    monkeypatch.setenv("PINOQIO_ENV_FILE", str(tmp_path / "none.env"))
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    try:
        stt.api_key()
    except RuntimeError as e:
        assert "ELEVENLABS_API_KEY" in str(e)
    else:
        raise AssertionError("expected RuntimeError")
