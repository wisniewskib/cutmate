import json
import sys

import pytest

from cutmate import doctor as dr
from cutmate import paths, tracks
from cutmate.cli import main
from cutmate.errors import CutmateError


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path))
    return tmp_path


def test_doctor_shape():
    d = dr.doctor()
    assert set(d) == {"python", "venv", "ffmpeg", "node", "packages", "cuda", "models", "keys", "carve", "config",
                      "plugin_root"}
    assert d["plugin_root"] == str(paths.plugin_root())
    assert set(d["packages"]) == {"faster_whisper", "mlx_whisper", "align", "track"}
    assert set(d["models"]) == {"whisper", "align_pl", "align_en", "pose", "hand"}
    assert all(isinstance(v, bool) for v in d["packages"].values())
    assert all(isinstance(v, bool) for v in d["models"].values())
    assert set(d["cuda"]) == {"libs", "devices", "errors"}
    assert set(d["keys"]) == set(dr.KEY_ENVS)


def test_doctor_never_prints_key_values(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-SECRET-1")
    d = dr.doctor()
    assert d["keys"]["OPENAI_API_KEY"] is True
    assert "sk-SECRET-1" not in json.dumps(d)
    assert main(["doctor"]) == 0
    assert "sk-SECRET-1" not in capsys.readouterr().out


def test_doctor_bad_config(home, capsys):
    (home / "config.json").write_text("{nope", encoding="utf-8")
    assert "invalid JSON" in dr.doctor()["config"]
    assert main(["doctor"]) == 0
    assert json.loads(capsys.readouterr().out)["config"] != "ok"


def test_doctor_cuda_safe(monkeypatch):
    monkeypatch.setitem(sys.modules, "ctranslate2", None)
    assert dr.doctor()["cuda"]["devices"] == 0


def _record(monkeypatch):
    snaps, kinds = [], []
    monkeypatch.setattr(dr, "_snapshot", lambda repo: snaps.append(repo) or f"/cache/{repo}")
    monkeypatch.setattr(tracks, "model_path", lambda kind="pose": kinds.append(kind) or f"/m/{kind}")
    return snaps, kinds


def test_download_models_local(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    snaps, kinds = _record(monkeypatch)
    dr.download_models("pl", "local")
    assert snaps == ["jonatasgrosman/wav2vec2-large-xlsr-53-polish", "Systran/faster-whisper-large-v3"]
    assert kinds == ["pose", "hand"]


def test_download_models_api_backend(monkeypatch):
    snaps, _ = _record(monkeypatch)
    dr.download_models("en", "groq")
    assert snaps == ["jonatasgrosman/wav2vec2-large-xlsr-53-english"]


def test_download_models_network_error(monkeypatch):
    def boom(repo):
        raise OSError("Connection refused")
    monkeypatch.setattr(dr, "_snapshot", boom)
    with pytest.raises(CutmateError, match=r"cannot download .*cutmate models"):
        dr.download_models("pl", "local")
