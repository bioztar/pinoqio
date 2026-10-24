from pinoqio.events import Chip, Contradiction, Verdict
from pinoqio.voice import PolicyState, cue_for, decide


def verdict(p=0.0, conf=None, chips=(), ask=None):
    c = Contradiction("it's forty-eight", "forty thousand", 3, conf) if conf is not None else None
    return Verdict(utterance_id=9, probability=p, verbal=p, vocal=0.0, chips=chips,
                   contradiction=c, ask_next=ask)


def test_quiet_below_threshold():
    _, a = decide(PolicyState(), verdict(0.59), 0.0)
    assert a is None


def test_whisper_at_threshold_short_cue():
    chips = (Chip("number_drift", "x", 0.5), Chip("hedging", "y", 0.2))
    s, a = decide(PolicyState(), verdict(0.6, chips=chips), 10.0)
    assert a.kind == "whisper" and a.text == "Number changed. Ask why."
    assert len(a.text.split()) <= 8 and s.last_whisper_t == 10.0


def test_whisper_rate_limited_8s():
    s, _ = decide(PolicyState(), verdict(0.9), 0.0)
    s, a = decide(s, verdict(0.9), 7.9)
    assert a is None
    _, a = decide(s, verdict(0.9), 8.0)
    assert a.kind == "whisper"


def test_interject_once_per_session():
    s, a = decide(PolicyState(), verdict(0.9, conf=0.85), 0.0)
    assert a.kind == "interject"
    assert "forty thousand" in a.text and "forty-eight" in a.text and "Which one is it?" in a.text
    assert s.interjected
    _, a = decide(s, verdict(0.9, conf=0.95), 100.0)
    assert a.kind == "whisper"  # second big contradiction only whispers


def test_low_confidence_contradiction_does_not_interject():
    _, a = decide(PolicyState(), verdict(0.7, conf=0.84), 0.0)
    assert a.kind == "whisper"


def test_ask_next_used_when_short_else_fallback():
    assert cue_for(verdict(0.7, ask="Why the new price?")) == "Why the new price?"
    long_ask = "Could you please explain in detail why the price moved so much"
    assert cue_for(verdict(0.7, ask=long_ask)) == "Possible bluff. Probe that."


def test_module_hooks_exist_for_app_and_server():
    from pinoqio import voice
    assert callable(voice.on_verdict) and callable(voice.interject)
