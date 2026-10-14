import pytest

from conftest import make_wav
from cutmate import music
from cutmate.errors import CutmateError
from cutmate.media import duration, integrated_lufs


def test_pick_source_priority(tmp_path):
    rec = tmp_path / "rec"
    (rec / "muzyka").mkdir(parents=True)
    make_wav(rec / "muzyka" / "b.mp3")
    make_wav(rec / "muzyka" / "a.wav")
    make_wav(rec / "own.wav")
    assert music.pick_source({"src": "own.wav"}, {"source": "folder", "folder": str(rec / "muzyka")}, rec) == rec / "own.wav"
    assert music.pick_source(None, {"source": "folder", "folder": str(rec / "muzyka")}, rec) == rec / "muzyka" / "a.wav"
    assert music.pick_source(None, {"source": "none"}, rec) is None
    with pytest.raises(CutmateError, match="not found"):
        music.pick_source({"src": "missing.mp3"}, None, rec)


def test_prepare_music_loops_and_levels(tmp_path):
    src = make_wav(tmp_path / "loop.wav", dur=2.0, amp=0.05)
    dst = music.prepare_music(src, tmp_path / "bgm" / "bed.m4a", 5.0)
    assert abs(duration(dst) - 5.0) < 0.1
    assert integrated_lufs(dst) == pytest.approx(-14, abs=1.5)


def test_carve_missing_script_is_soft(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(music, "_carve_script", lambda: None)
    assert music.carve(tmp_path) is False
    assert "WARN" in capsys.readouterr().out
