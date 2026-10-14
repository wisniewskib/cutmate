import json
import subprocess

import pytest

from conftest import make_clip
from cutmate import render as R
from cutmate.errors import CutmateError


def setup_out(tmp_path):
    out = tmp_path / "out"
    (out / "composition").mkdir(parents=True)
    (out / "work").mkdir()
    (out / "composition" / "index.html").write_text("<html></html>", encoding="utf-8")
    (out / "work" / "checkpoints.json").write_text(json.dumps([0.5, 1.5]), encoding="utf-8")
    return out


def test_requires_build(tmp_path):
    with pytest.raises(CutmateError, match="cutmate build"):
        R.render(tmp_path)


def test_check_failure_stops(tmp_path, monkeypatch):
    out = setup_out(tmp_path)
    monkeypatch.setattr(R, "run", lambda cmd, cwd=None, env=None: subprocess.CompletedProcess(cmd, 1, "lint error: x", ""))
    monkeypatch.setattr(R, "hf", lambda *a: ["hf", *a])
    with pytest.raises(CutmateError, match="lint error"):
        R.render(out)


def test_render_then_finalize(tmp_path, monkeypatch):
    out = setup_out(tmp_path)
    monkeypatch.setattr(R, "run", lambda cmd, cwd=None, env=None: subprocess.CompletedProcess(cmd, 0, "Check passed", ""))
    monkeypatch.setattr(R, "hf", lambda *a: ["hf", *a])

    def fake_stream(cmd, cwd):
        make_clip(out / "work" / "render.mp4", dur=2.0, gaps=())
        return 0
    monkeypatch.setattr(R, "_stream", fake_stream)
    r = R.render(out)
    assert r["ok"] and (out / "final.mp4").exists()
    assert [p.name for p in r["frames"]] == ["check_0_50.png", "check_1_50.png"]
