import pytest

from cutmate.finalize import finalize
from conftest import make_clip


def test_finalize_ok_and_frames(tmp_path):
    src = make_clip(tmp_path / "render.mp4", amp=0.05)
    r = finalize(src, tmp_path / "final.mp4", "9:16", check=[0.5, 2.25])
    assert r["ok"]
    assert r["lufs"] == pytest.approx(-14, abs=1.0)
    assert [p.name for p in r["frames"]] == ["check_0_50.png", "check_2_25.png"]
    assert all(p.exists() for p in r["frames"])


def test_finalize_flags_wrong_format(tmp_path):
    src = make_clip(tmp_path / "render.mp4")
    r = finalize(src, tmp_path / "final.mp4", "16:9")
    assert not r["ok"]


def test_finalize_bad_format_fails_before_encoding(tmp_path):
    from cutmate.errors import CutmateError
    src = make_clip(tmp_path / "render.mp4")
    with pytest.raises(CutmateError, match="unknown format"):
        finalize(src, tmp_path / "final.mp4", "4:3")
    assert not list(tmp_path.glob("final*"))


def test_finalize_failure_keeps_existing_dst(tmp_path, monkeypatch):
    import subprocess
    from cutmate import finalize as fin
    from cutmate.errors import MediaError
    src = make_clip(tmp_path / "render.mp4")
    dst = tmp_path / "final.mp4"
    dst.write_bytes(b"previous")
    real_run = fin.run

    def failing(cmd):
        if str(cmd[-1]).endswith("final.tmp.mp4"):
            return subprocess.CompletedProcess(cmd, 1, "", "boom")
        return real_run(cmd)

    monkeypatch.setattr(fin, "run", failing)
    with pytest.raises(MediaError, match="finalize failed"):
        fin.finalize(src, dst)
    assert dst.read_bytes() == b"previous" and not (tmp_path / "final.tmp.mp4").exists()
