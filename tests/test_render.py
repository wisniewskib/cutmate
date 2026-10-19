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

    def fake_stream(cmd, cwd, log=None):
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

    def fake_stream(cmd, cwd, log=None):
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

    def fake_stream(cmd, cwd, log=None):
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

    def fake_stream(cmd, cwd, log=None):
        make_clip(out / "work" / "render.mp4", dur=2.0, gaps=())
        return 0
    monkeypatch.setattr(R, "_stream", fake_stream)

    with pytest.raises(CutmateError, match="malformed checkpoints.json"):
        R.render(out)


def test_render_clears_old_check_frames(tmp_path, monkeypatch):
    out = setup_out(tmp_path)
    (out / "check_9_99.png").write_bytes(b"old")
    monkeypatch.setattr(R, "run", lambda cmd, cwd=None, env=None: subprocess.CompletedProcess(cmd, 0, "Check passed", ""))
    monkeypatch.setattr(R, "hf", lambda *a: ["hf", *a])

    def fake_stream(cmd, cwd, log=None):
        make_clip(out / "work" / "render.mp4", dur=2.0, gaps=())
        return 0
    monkeypatch.setattr(R, "_stream", fake_stream)
    R.render(out)
    assert not (out / "check_9_99.png").exists() and (out / "check_0_50.png").exists()


def test_render_uses_project_format(tmp_path, monkeypatch):
    out = setup_out(tmp_path)
    (out / "edl.json").write_text('{"format": "16:9", "segments": []}', encoding="utf-8")
    monkeypatch.setattr(R, "run", lambda cmd, cwd=None, env=None: subprocess.CompletedProcess(cmd, 0, "Check passed", ""))
    monkeypatch.setattr(R, "hf", lambda *a: ["hf", *a])

    def fake_stream(cmd, cwd, log=None):
        (out / "work" / "render.mp4").write_bytes(b"v")
        return 0
    monkeypatch.setattr(R, "_stream", fake_stream)
    seen = {}

    def fake_finalize(src, dst, fmt, check=()):
        seen["fmt"] = fmt
        return {"ok": True}
    monkeypatch.setattr(R, "finalize", fake_finalize)
    R.render(out)
    assert seen["fmt"] == "16:9"


def test_stream_writes_log(tmp_path, capsys):
    import sys
    log = tmp_path / "work" / "render.log"
    log.parent.mkdir()
    log.write_text("old\n", encoding="utf-8")
    code = R._stream([sys.executable, "-c", "print('a'); print('b')"], tmp_path, log)
    assert code == 0
    assert log.read_text(encoding="utf-8") == "a\nb\n"
    assert capsys.readouterr().out == "a\nb\n"


def _deadline_then(codes):
    calls = []

    def fake_run(cmd, cwd=None, env=None):
        calls.append(cmd)
        code = codes[len(calls) - 1]
        out = "check_runtime_failure: Check did not finish within its deadline." if code == "deadline" else "Check passed"
        return subprocess.CompletedProcess(cmd, 1 if code == "deadline" else code, out, "")
    return calls, fake_run


def test_check_waits_for_render_ready_and_retries_a_deadline_once(tmp_path):
    from cutmate.hf import CHECK_TIMEOUT_MS, check
    calls, fake = _deadline_then(["deadline", 0])
    r = check(tmp_path, fake, lambda *a: ["hf", *a])
    assert r.returncode == 0 and len(calls) == 2
    assert calls[0] == ["hf", "check", "--timeout", str(CHECK_TIMEOUT_MS)] and CHECK_TIMEOUT_MS >= 30000


def test_check_deadline_twice_is_a_one_line_busy_error(tmp_path):
    from cutmate.hf import check
    calls, fake = _deadline_then(["deadline", "deadline"])
    with pytest.raises(CutmateError, match="too busy") as e:
        check(tmp_path, fake, lambda *a: ["hf", *a])
    assert "\n" not in str(e.value) and len(calls) == 2


def test_check_real_failure_is_not_retried(tmp_path):
    from cutmate.hf import check
    calls, fake = _deadline_then([1])
    assert check(tmp_path, fake, lambda *a: ["hf", *a]).returncode == 1 and len(calls) == 1
