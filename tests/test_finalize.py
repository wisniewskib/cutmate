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
