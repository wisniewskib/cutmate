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


def test_carve_script_picks_newest_version(tmp_path, monkeypatch):
    base = tmp_path / ".claude" / "plugins" / "cache" / "hyperframes"
    for v in ("0.8.9", "0.8.157", "0.8.20"):
        f = base / "hyperframes" / v / "skills" / "hyperframes-audio" / "scripts" / "carve.mjs"
        f.parent.mkdir(parents=True)
        f.write_text("")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert "/0.8.157/" in music._carve_script()


def test_carve_script_found_under_cutmate_marketplace(tmp_path, monkeypatch):
    # one-marketplace install: HyperFrames comes from cutmate's own marketplace
    f = tmp_path / ".claude/plugins/cache/cutmate/hyperframes/0.8.157/skills/hyperframes-audio/scripts/carve.mjs"
    f.parent.mkdir(parents=True)
    f.write_text("")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert music._carve_script() == str(f)


def test_carve_script_prefers_pinned_version_and_new_layout(tmp_path, monkeypatch):
    cache = tmp_path / ".claude/plugins/cache"
    newer = cache / "hyperframes/hyperframes/9.9.9/skills/media-use/audio/scripts/carve.mjs"
    pinned = cache / f"cutmate/hyperframes/{music.HF_VERSION}/skills/media-use/audio/scripts/carve.mjs"
    for f in (newer, pinned):
        f.parent.mkdir(parents=True)
        f.write_text("")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert music._carve_script() == str(pinned)
    pinned.unlink()
    assert music._carve_script() == str(newer)


def test_carve_installs_pinned_core(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(music, "_carve_script", lambda: "carve.mjs")
    monkeypatch.setattr(music.shutil, "which", lambda n: n)

    def fake_run(cmd, cwd=None, env=None):
        import subprocess
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(music, "run", fake_run)
    assert music.carve(tmp_path) is True
    assert "@hyperframes/core@0.8.157" in calls[0]
