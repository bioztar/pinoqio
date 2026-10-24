from dataclasses import FrozenInstanceError

import pytest

from pinoqio.events import Utterance


def test_utterance_is_immutable():
    u = Utterance(id=1, speaker="them", text="hi", t_start=0.0, t_end=1.0)
    with pytest.raises(FrozenInstanceError):
        u.text = "x"  # type: ignore[misc]
