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


def test_stale_render_cleared(tmp_path, monkeypatch):
    """Pre-existing render.mp4 without a new write should fail."""
    out = setup_out(tmp_path)
    # Pre-create an old render file
    make_clip(out / "work" / "render.mp4", dur=1.0, gaps=())
    monkeypatch.setattr(R, "run", lambda cmd, cwd=None, env=None: subprocess.CompletedProcess(cmd, 0, "Check passed", ""))
    monkeypatch.setattr(R, "hf", lambda *a: ["hf", *a])

    def fake_stream(cmd, cwd):
        # Return 0 but don't write the file (simulating failed render that returns success code)
        return 0
    monkeypatch.setattr(R, "_stream", fake_stream)
    with pytest.raises(CutmateError, match="hyperframes render failed"):
        R.render(out)


def test_cwd_and_output_path(tmp_path, monkeypatch):
    """Verify that _stream receives correct cwd and relative output path."""
    out = setup_out(tmp_path)

    captured_calls = {"run": [], "_stream": []}

    def fake_hf(*a):
        return ["hf", *a]
    monkeypatch.setattr(R, "hf", fake_hf)

    def fake_run(cmd, cwd=None, env=None):
        captured_calls["run"].append((cmd, cwd))
        return subprocess.CompletedProcess(cmd, 0, "Check passed", "")
    monkeypatch.setattr(R, "run", fake_run)

    def fake_stream(cmd, cwd):
        captured_calls["_stream"].append((cmd, cwd))
        make_clip(out / "work" / "render.mp4", dur=2.0, gaps=())
        return 0
    monkeypatch.setattr(R, "_stream", fake_stream)

    r = R.render(out)

    # Verify run was called with hf("check") and cwd=proj
    assert any(cmd[0:2] == ["hf", "check"] and cwd == out / "composition" for cmd, cwd in captured_calls["run"]), \
        f"Expected run(hf('check'), cwd=proj). Got {captured_calls['run']}"

    # Verify _stream was called with relative path and correct cwd
    stream_cmd, stream_cwd = captured_calls["_stream"][0]
    assert stream_cwd == out / "composition", f"Expected cwd={out / 'composition'}, got {stream_cwd}"
    assert "-o" in stream_cmd and "../work/render.mp4" in stream_cmd, \
        f"Expected '-o ../work/render.mp4' in cmd. Got {stream_cmd}"
    assert str(out / "composition") not in stream_cmd, \
        f"Expected proj not in args. Got {stream_cmd}"


def test_malformed_checkpoints(tmp_path, monkeypatch):
    """Malformed checkpoints.json should raise one-line CutmateError."""
    out = setup_out(tmp_path)
    (out / "work" / "checkpoints.json").write_text("{ invalid json }", encoding="utf-8")
    monkeypatch.setattr(R, "run", lambda cmd, cwd=None, env=None: subprocess.CompletedProcess(cmd, 0, "Check passed", ""))
    monkeypatch.setattr(R, "hf", lambda *a: ["hf", *a])

    def fake_stream(cmd, cwd):
        make_clip(out / "work" / "render.mp4", dur=2.0, gaps=())
        return 0
    monkeypatch.setattr(R, "_stream", fake_stream)

    with pytest.raises(CutmateError, match="malformed checkpoints.json"):
        R.render(out)
