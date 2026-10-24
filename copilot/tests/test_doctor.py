import numpy as np

from pinoqio import doctor
from pinoqio.doctor import FAIL, OK, WARN

BATT_AC = "Now drawing from 'AC Power'\n -InternalBattery-0 (id=1)\t87%; charging; 0:30 remaining"
BATT_BAT = "Now drawing from 'Battery Power'\n -InternalBattery-0 (id=1)\t23%; discharging"


def test_rms_silence_and_tone():
    assert doctor.rms(np.zeros(100, dtype=np.int16)) == 0.0
    assert doctor.rms(np.array([], dtype=np.int16)) == 0.0
    tone = (np.sin(np.linspace(0, 200, 16000)) * 8000).astype(np.int16)
    assert 0.1 < doctor.rms(tone) < 0.25


def test_silent_blackhole_is_red_with_hint():
    r = doctor.signal_result(0.0)
    assert r.status == FAIL and "Multi-Output" in r.detail
    assert doctor.signal_result(0.05).status == OK


def test_device_match_is_case_insensitive_and_reports_missing():
    names = ["BlackHole 2ch", "MacBook Air Microphone"]
    assert doctor.device_result("x", "blackhole 2ch", names).status == OK
    r = doctor.device_result("x", "Shokz", names)
    assert r.status == FAIL and "BlackHole 2ch" in r.detail


def test_keys_names_only():
    r = doctor.keys_result({"GEMINI_API_KEY": "secret-abc", "ELEVENLABS_API_KEY": "secret-def"})
    assert r.status == FAIL and r.detail == "missing NEBIUS_API_KEY" and "secret" not in r.detail
    full = doctor.keys_result({k: "v" for k in doctor.KEYS})
    assert full.status == OK and full.detail == ", ".join(doctor.KEYS)


def test_latency_slow_is_warn():
    assert doctor.latency_result("g", 2.0, 5.0).status == OK
    assert doctor.latency_result("g", 6.0, 5.0).status == WARN


def test_parse_batt():
    assert doctor.parse_batt(BATT_AC) == (87, True)
    assert doctor.parse_batt(BATT_BAT) == (23, False)
    assert doctor.parse_batt("Now drawing from 'AC Power'") == (None, True)


def test_power_results():
    batt, adapter = doctor.power_result(BATT_BAT)
    assert batt.status == FAIL and adapter.status == FAIL
    assert [r.status for r in doctor.power_result(BATT_AC)] == [OK, OK]


def test_disk():
    assert doctor.disk_result(int(50e9)).status == OK
    assert doctor.disk_result(int(1e9)).status == FAIL


def test_render_marks_each_line():
    out = doctor.render([doctor.Result("a", OK, "fine"), doctor.Result("b", FAIL)])
    assert out.count("\n") == 1 and "a  fine" in out
