from pathlib import Path

import numpy as np

from demo.make_replay import RATE, build_timeline, parse_script

SCRIPT = Path(__file__).resolve().parents[1] / "demo" / "script.md"


def test_script_parses_alternating_numbered_lines():
    lines = parse_script(SCRIPT.read_text())
    assert [l.n for l in lines] == list(range(1, len(lines) + 1))
    assert {l.role for l in lines} == {"BUYER", "SUPPLIER"}
    assert len(lines) >= 25


def test_timeline_aligned_equal_length():
    lines = parse_script("1. **BUYER** [0.5]: hi\n2. **SUPPLIER** [1.0]: yo\n")
    clips = {1: np.ones(RATE, dtype=np.int16), 2: np.full(RATE // 2, 2, dtype=np.int16)}
    out = build_timeline(lines, clips)
    assert len(out["me"]) == len(out["them"])
    assert out["me"][int(0.5 * RATE)] == 1 and out["me"][int(0.5 * RATE) - 1] == 0
    start2 = int(0.5 * RATE) + RATE + RATE
    assert out["them"][start2] == 2 and out["me"][start2] == 0
