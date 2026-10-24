import numpy as np

from pinoqio import prosody
from pinoqio.prosody import SR, Baseline


def tone(hz: float, secs: float, amp: float = 8000) -> np.ndarray:
    t = np.arange(int(SR * secs)) / SR
    return (amp * np.sin(2 * np.pi * hz * t)).astype(np.int16)


def silence(secs: float) -> np.ndarray:
    return np.zeros(int(SR * secs), np.int16)


def test_pitch_of_tone():
    feats = prosody.pitch_stats(tone(200, 1.0))
    assert abs(feats["pitch_mean_hz"] - 200) < 5
    assert feats["pitch_sd_hz"] < 5


def test_pitch_empty_on_silence():
    assert prosody.pitch_stats(silence(1.0)) == {}


def test_trim_silence():
    audio = np.concatenate([silence(0.5), tone(200, 1.0), silence(0.5)])
    start, end = prosody.trim_silence(audio)
    assert abs(start / SR - 0.5) < 0.05
    assert abs(end / SR - 1.5) < 0.05


def test_pause_ratio():
    audio = np.concatenate([tone(200, 0.5), silence(0.5), tone(200, 0.5)])
    assert abs(prosody.pause_ratio(audio) - 1 / 3) < 0.05
    assert prosody.pause_ratio(tone(200, 1.0)) == 0.0


def test_filler_count():
    text = "Um, well, I mean, it's like, you know, uh, fine. Umbrella and wellness don't count."
    assert prosody.filler_count(text) == 6


def test_rate_and_extract():
    feats = prosody.extract(tone(200, 2.0), "one two three four")
    assert feats["rate_wps"] == 2.0
    assert feats["filler_count"] == 0.0


def test_z_zero_until_three_samples():
    base = Baseline()
    for v in (1.0, 2.0):
        assert prosody.with_z({"x": v}, base)["x_z"] == 0.0
        base = base.update({"x": v})
    assert prosody.with_z({"x": 5.0}, base)["x_z"] == 0.0
    base = base.update({"x": 3.0})
    z = prosody.with_z({"x": 3.0}, base)["x_z"]  # mean 2, pstdev ~0.816
    assert abs(z - 1.2247) < 1e-3


def test_baseline_is_immutable():
    base = Baseline()
    new = base.update({"x": 1.0})
    assert base.samples == {} and new.samples == {"x": (1.0,)}


def test_z_is_floored_and_capped():
    from pinoqio.prosody import Baseline, with_z
    b = Baseline(samples={"filler_count": (0.0, 0.0, 0.0)})
    z = with_z({"filler_count": 2.0}, b)["filler_count_z"]
    assert 2.0 < z <= 4.0
