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
    assert cfg.music == {"source": "none", "folder": None, "volume": 0.45}


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


@pytest.mark.parametrize("music", [{"source": "spotify"}, {"volume": True}, {"volume": 3}, {"volume": "x"}])
def test_load_rejects_bad_music(tmp_path, music):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"music": music}), encoding="utf-8")
    with pytest.raises(ConfigError, match="music"):
        config.load(p)


def test_set_values_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    config.set_values(["language=en", "steps.qa=false", "captions.9:16=srt", "music.volume=0.3"], p)
    cfg = config.load(p)
    assert cfg.language == "en"
    assert cfg.steps == {"factcheck": True, "qa": False, "thumbnail": True}
    assert cfg.captions["9:16"] == "srt"
    assert cfg.music["volume"] == 0.3


def test_set_values_unknown_key_hides_value(tmp_path):
    p = tmp_path / "config.json"
    with pytest.raises(ConfigError) as e:
        config.set_values(["GROQ_API_KEY=gsk_secret123"], p)
    msg = str(e.value)
    assert "environment variables" in msg and "gsk_secret123" not in msg
    assert not p.exists()


def test_set_values_pair_without_equals_hides_text(tmp_path):
    p = tmp_path / "config.json"
    with pytest.raises(ConfigError) as e:
        config.set_values(["gsk_secret123"], p)
    msg = str(e.value)
    assert "config set expects KEY=VALUE pairs" in msg and "gsk_secret123" not in msg
    assert not p.exists()


def test_set_values_folder_needs_audio(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ConfigError, match="empty"):
        config.set_values(["music.source=folder", f"music.folder={empty}"], p)
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "notes.txt").write_text("x")
    with pytest.raises(ConfigError, match="notes"):
        config.set_values(["music.source=folder", f"music.folder={notes}"], p)
    home = tmp_path / "h"
    (home / "tunes").mkdir(parents=True)
    (home / "tunes" / "a.mp3").write_bytes(b"x")
    monkeypatch.setenv("HOME", str(home))
    cfg = config.set_values(["music.source=folder", "music.folder=~/tunes"], p)
    assert "~" not in cfg.music["folder"]
    assert cfg.music["folder"] == str((home / "tunes").resolve())
    assert config.load(p).music["folder"] == cfg.music["folder"]


def test_set_values_bad_theme(tmp_path):
    with pytest.raises(CutmateError, match="nope"):
        config.set_values(["theme=nope"], tmp_path / "config.json")


def test_set_values_atomic(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"language": "pl"}), encoding="utf-8")
    with pytest.raises(ConfigError):
        config.set_values(["language=en", "steps.qa=maybe"], p)
    assert config.load(p).language == "pl"


def test_set_values_rewrites_broken_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path))
    p = tmp_path / "config.json"
    p.write_text("{nope", encoding="utf-8")
    config.set_values(["language=en"])
    assert config.load(p).language == "en"
    assert "WARN config:" in capsys.readouterr().out
