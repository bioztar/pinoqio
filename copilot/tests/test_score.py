from pinoqio.analyst import Analysis, NumberDrift
from pinoqio.events import Contradiction
from pinoqio.score import MAX_PROB, VOCAL_CAP, score


def test_neutral_is_low_and_chipless():
    v = score(Analysis(utterance_id=3), {})
    assert v.utterance_id == 3
    assert v.probability < 0.15 and v.chips == () and v.contradiction is None


def test_contradiction_dominates_and_carries_through():
    c = Contradiction("48k", "40k", 1, 0.9)
    v = score(Analysis(utterance_id=2, contradiction=c, ask_next="Why?"), {})
    assert v.probability > 0.8
    assert v.contradiction == c and v.ask_next == "Why?"
    assert v.chips[0].kind == "contradiction" and "40k" in v.chips[0].label


def test_verbal_order():
    p = lambda **kw: score(Analysis(**kw), {}).probability
    contra = p(contradiction=Contradiction("a", "b", 0, 0.9))
    drift = p(number_drift=NumberDrift("price", "40k", "48k"))
    evasion = p(evasion=0.9)
    hedge = p(hedging=0.9)
    assert contra > drift > evasion > hedge > p()


def test_drift_label_has_time_and_values():
    v = score(Analysis(number_drift=NumberDrift("price", "40k", "48k", 42.0)), {})
    assert v.chips[0].label == "Price: 40k at 0:42, now 48k"


def test_vocal_alone_can_say_probably_false_but_is_capped():
    pros = {k: 9.0 for k in ("pitch_mean_hz_z", "latency_s_z", "pause_ratio_z", "rate_wps_z", "filler_count_z")}
    v = score(Analysis(), pros)
    assert 0.5 < v.probability < 0.7  # demo parity: strong voice stress alone reads "probably false"
    assert v.vocal == v.probability
    assert sum(c.weight for c in v.chips) * 4.0 <= VOCAL_CAP + 0.01
    assert {c.kind for c in v.chips} <= {"pitch", "latency", "pause", "rate", "filler"}


def test_small_z_ignored_and_pitch_down_ignored():
    v = score(Analysis(), {"pitch_mean_hz_z": -2.5, "latency_s_z": 0.5})
    assert v.chips == () and v.vocal == v.probability


def test_rate_either_direction():
    assert score(Analysis(), {"rate_wps_z": -2.0}).vocal > score(Analysis(), {}).vocal


def test_probability_never_above_cap():
    a = Analysis(
        contradiction=Contradiction("a", "b", 0, 1.0),
        number_drift=NumberDrift("p", "1", "2"),
        evasion=1.0,
        hedging=1.0,
    )
    v = score(a, {"pitch_mean_hz_z": 3.0})
    assert v.probability == MAX_PROB
    assert [c.kind for c in v.chips][0] == "contradiction"
