import pytest

from pinoqio import config


def test_missing_key_names_setting(monkeypatch, tmp_path):
    monkeypatch.setenv("PINOQIO_ENV_FILE", str(tmp_path / "none.env"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        config.gemini_key()


def test_loads_from_env_file(monkeypatch, tmp_path):
    f = tmp_path / "x.env"
    f.write_text("ELEVENLABS_API_KEY=abc\n")
    monkeypatch.setenv("PINOQIO_ENV_FILE", str(f))
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert config.elevenlabs_key() == "abc"
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
