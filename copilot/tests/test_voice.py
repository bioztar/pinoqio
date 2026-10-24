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


def test_say_it_button_speaks_every_press(monkeypatch):
    import asyncio
    from pinoqio import voice
    spoken = []

    async def fake_speak(self, text, device_name):
        spoken.append(text)

    monkeypatch.setattr(voice.Voice, "_speak", fake_speak)
    monkeypatch.setattr(voice, "_voice", None)

    async def press_twice():
        await voice.interject("one")
        await voice.interject("two")

    asyncio.run(press_twice())
    assert spoken == ["one", "two"]


def _verdict_with(chips=(), contradiction=None):
    from pinoqio.events import Verdict
    return Verdict(utterance_id=9, probability=0.9, verbal=0.9, vocal=0.1, chips=tuple(chips), contradiction=contradiction)


def test_public_mode_calls_out_each_inconsistency_once():
    from pinoqio.events import Chip, Contradiction
    from pinoqio.voice import PolicyState, decide_public
    price = _verdict_with(contradiction=Contradiction("it is 48,000", "the price is 40,000", 3, 0.7))
    delivery = _verdict_with(chips=[Chip("number_drift", "Delivery date: March at 0:25, now end of April", 0.5)])
    s, a1 = decide_public(PolicyState(), price)
    s, again = decide_public(s, price)
    s, a2 = decide_public(s, delivery)
    assert a1 and a1.kind == "interject" and "40,000" in a1.text
    assert again is None
    assert a2 and "end of April" in a2.text


def test_public_mode_ignores_plain_hedging():
    from pinoqio.events import Chip
    from pinoqio.voice import PolicyState, decide_public
    _, a = decide_public(PolicyState(), _verdict_with(chips=[Chip("hedging", "Hedging: maybe", 0.3)]))
    assert a is None
