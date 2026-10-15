import json

import pytest

from cutmate import config
from cutmate.errors import ConfigError, CutmateError
from cutmate.formats import size_of


def test_size_of():
    assert size_of("9:16") == (1080, 1920)
    assert size_of("16:9") == (1920, 1080)
    with pytest.raises(CutmateError):
        size_of("4:3")


def test_load_missing_returns_defaults(tmp_path):
    cfg = config.load(tmp_path / "config.json")
    assert cfg.transcription == "local"
    assert cfg.language == "pl"
    assert cfg.theme == "clean"
    assert cfg.steps == {"factcheck": True, "qa": True, "thumbnail": True}
    assert cfg.music == {"source": "none", "folder": None}


def test_save_load_roundtrip(tmp_path):
    p = tmp_path / "sub" / "config.json"
    cfg = config.Config(transcription="groq", language="en", steps={"factcheck": False})
    config.save(cfg, p)
    back = config.load(p)
    assert back.transcription == "groq"
    assert back.language == "en"
    # missing step keys fall back to defaults
    assert back.steps == {"factcheck": False, "qa": True, "thumbnail": True}


def test_load_rejects_bad_backend(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"transcription": "whisperx"}), encoding="utf-8")
    with pytest.raises(ConfigError, match="transcription"):
        config.load(p)


def test_load_rejects_bad_json(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{nope", encoding="utf-8")
    with pytest.raises(ConfigError, match="/cutmate:setup"):
        config.load(p)


def test_home_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path))
    assert config.home() == tmp_path


def test_load_rejects_non_object_json(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps([]), encoding="utf-8")
    with pytest.raises(ConfigError, match="must be a JSON object"):
        config.load(p)


def test_load_rejects_steps_as_string(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"steps": "invalid"}), encoding="utf-8")
    with pytest.raises(ConfigError, match="steps must be a JSON object"):
        config.load(p)


def test_load_rejects_music_as_list(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"music": [1, 2, 3]}), encoding="utf-8")
    with pytest.raises(ConfigError, match="music must be a JSON object"):
        config.load(p)


def test_load_rejects_path_as_directory(tmp_path):
    # Create a directory instead of a file
    config_dir = tmp_path / "config.json"
    config_dir.mkdir()
    with pytest.raises(ConfigError, match="/cutmate:setup"):
        config.load(config_dir)


def test_load_rejects_invalid_language(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"language": "fr"}), encoding="utf-8")
    with pytest.raises(ConfigError, match="language"):
        config.load(p)


def test_captions_defaults_and_merge(tmp_path):
    from cutmate import config
    assert config.load(tmp_path / "none.json").captions == {"9:16": "burn", "16:9": "srt"}
    p = tmp_path / "c.json"
    p.write_text('{"captions": {"16:9": "both"}}', encoding="utf-8")
    assert config.load(p).captions == {"9:16": "burn", "16:9": "both"}


@pytest.mark.parametrize("bad, msg", [('{"captions": "srt"}', "captions must be a JSON object"),
                                      ('{"captions": {"16:9": "subs"}}', "burn, srt, both, none"),
                                      ('{"captions": {"4:3": "srt"}}', "4:3")])
def test_captions_invalid(tmp_path, bad, msg):
    from cutmate import config
    from cutmate.errors import ConfigError
    p = tmp_path / "c.json"
    p.write_text(bad, encoding="utf-8")
    with pytest.raises(ConfigError, match=msg):
        config.load(p)
