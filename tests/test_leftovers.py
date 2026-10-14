import json
import sys
from types import SimpleNamespace

import pytest

from conftest import make_clip, make_wav
from cutmate.backends import local
from cutmate.backends.local import LocalBackend
from cutmate.cut import cut_aroll, load_timed
from cutmate.errors import BackendError, CutmateError


def test_null_id_gets_generated(tmp_path):
    rec = tmp_path / "rec"
    make_clip(rec / "take1.mp4")
    (rec / "out").mkdir()
    edl = rec / "out" / "edl.json"
    edl.write_text(json.dumps({"segments": [{"id": None, "file": "take1.mp4", "in": 0.0, "out": 1.0, "text": "raz"}]}),
                   encoding="utf-8")
    timed = cut_aroll(edl)
    assert timed[0]["id"] == "S1"


def test_load_timed_missing(tmp_path):
    with pytest.raises(CutmateError, match="cutmate cut"):
        load_timed(tmp_path)


def test_load_timed_old_file_without_ids(tmp_path):
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "edl_timed.json").write_text(json.dumps([{"start": 0, "end": 1, "text": "x"}]), encoding="utf-8")
    with pytest.raises(CutmateError, match="older cutmate"):
        load_timed(tmp_path)


def test_cpu_rebuild_failure_is_backend_error(monkeypatch, tmp_path):
    class FakeWhisperModel:
        def __init__(self, model, device="cpu", compute_type="int8"):
            if device == "cpu":
                raise MemoryError("not enough RAM")
            self.device = device

        def transcribe(self, *a, **k):
            raise RuntimeError("libcublas.so.12 not found")

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeWhisperModel))
    monkeypatch.setattr(local, "pick_device", lambda: ("cuda", "float16"))
    with pytest.raises(BackendError, match="local model load failed"):
        LocalBackend("faster", "large-v3").transcribe(make_wav(tmp_path / "a.wav"), "pl")
