import numpy as np
import pytest
import soundfile as sf

from pinoqio import audio, ears, stt


def write_wav(path, secs=1.0):
    t = np.arange(int(16_000 * secs)) / 16_000
    sf.write(str(path), 0.5 * np.sin(2 * np.pi * 200 * t), 16_000, subtype="PCM_16")


def fake_segments(script):
    """segments_fn yielding scripted (text, t_start, t_end) per speaker, ignoring chunks."""

    async def fn(chunks, speaker):
        async for _ in chunks:  # drain so replay finishes
            pass
        for text, a, b in script[speaker]:
            n = int((b - a) * 16_000)
            audio_ = (np.sin(np.arange(n) / 5) * 8000).astype(np.int16)
            yield stt.Segment(speaker, text, audio_, a, b)

    return fn


async def test_replay_ids_speakers_latency(tmp_path):
    me, them = tmp_path / "me.wav", tmp_path / "them.wav"
    write_wav(me)
    write_wav(them)
    script = {"me": [("what is the price", 0.0, 1.0)], "them": [("forty k", 2.5, 3.0)]}
    out = [
        u async for u in ears.utterances(
            "replay", them, me, realtime=False, segments_fn=fake_segments(script)
        )
    ]
    by_speaker = {u.speaker: u for u in out}
    assert sorted(u.id for u in out) == [1, 2]
    assert by_speaker["me"].t_end == 1.0
    assert "latency_s" not in by_speaker["me"].prosody
    if by_speaker["them"].id > by_speaker["me"].id:  # me arrived first
        assert by_speaker["them"].prosody["latency_s"] == pytest.approx(1.5)
    assert by_speaker["them"].prosody["rate_wps_z"] == 0.0


async def test_replay_needs_both_wavs():
    with pytest.raises(ValueError):
        async for _ in ears.utterances("replay"):
            pass


def test_missing_device_names_it(monkeypatch):
    monkeypatch.setattr(audio.sd, "query_devices", lambda: [{"name": "Speakers", "max_input_channels": 0}])
    with pytest.raises(audio.DeviceNotFound, match="Nonexistent Mic"):
        audio.find_device("Nonexistent Mic")


def test_to_mono_int16():
    block = np.array([[100, 300], [-100, -300]], np.int16)
    assert audio.to_mono_int16(block).tolist() == [200, -200]
