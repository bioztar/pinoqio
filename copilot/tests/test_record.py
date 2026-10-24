import json

from pinoqio import record
from pinoqio.events import Utterance, Verdict


async def _stream():
    yield Utterance(1, "them", "forty thousand", 0.0, 1.0, {})
    yield Verdict(1, 0.2, 0.1, 0.3)


async def test_recording_writes_offsets_and_passes_events_through(tmp_path):
    ticks = iter([100.0, 100.5, 103.25])
    path = tmp_path / "e.jsonl"
    out = [e async for e in record.recording(_stream(), path, clock=lambda: next(ticks))]
    assert [type(e) for e in out] == [Utterance, Verdict]
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert [(l["t"], l["type"]) for l in lines] == [(0.5, "utterance"), (3.25, "verdict")]
    assert lines[0]["text"] == "forty thousand"
    assert record.load(path) == tuple(lines)


async def test_play_honours_offsets_and_strips_t():
    events = ({"t": 1.0, "type": "utterance", "id": 1}, {"t": 4.0, "type": "verdict", "utterance_id": 1})
    now, sent, slept = [0.0], [], []

    async def sleep(s):
        slept.append(s)
        now[0] += s

    async def send(m):
        sent.append((now[0], m))

    await record.play(events, send, clock=lambda: now[0], sleep=sleep)
    assert slept == [1.0, 3.0]
    assert sent == [(1.0, {"type": "utterance", "id": 1}), (4.0, {"type": "verdict", "utterance_id": 1})]
