import json
import shutil

import pytest

from cutmate import config, media, smoke as sm
from cutmate.transcript import Transcript, Word
from conftest import make_clip


@pytest.fixture
def calls(monkeypatch):
    rec = {}

    def fake_build(out, **kw):
        rec["build"] = dict(kw, out=out)
        return {"warnings": []}

    def fake_render(out):
        shutil.copy(out / "aroll.mp4", out / "final.mp4")
        return {"ok": True, "lufs": -14.0}

    monkeypatch.setattr(sm, "build", fake_build)
    monkeypatch.setattr(sm, "render", fake_render)
    return rec


def _load(workdir, name):
    return json.loads((workdir / "rec" / "out" / name).read_text(encoding="utf-8"))


class Fake:
    name = "fake"

    def transcribe(self, wav, language, prompt=None):
        return Transcript(language, [Word("Cześć", 0.2, 0.6)], "fake")


def test_smoke_synthetic(tmp_path, calls):
    cfg = config.Config()
    r = sm.smoke(tmp_path, cfg)
    out = tmp_path / "rec" / "out"
    assert media.duration(out / "aroll.mp4") == pytest.approx(5.0, abs=0.1)
    words = _load(tmp_path, "work/aligned_words.json")
    assert words[0]["word"] == "To" and words[-1]["end"] <= 5.0
    assert _load(tmp_path, "plan.json")["graphics"][0]["text"] == "Działa!"
    b = calls["build"]
    assert b["theme"] == cfg.theme and b["captions"] == cfg.captions and b["music"] == cfg.music
    assert r["ok"] and r["lufs"] == -14.0 and r["frame"].exists()


def test_smoke_clip_words(tmp_path, calls):
    src = make_clip(tmp_path / "in.mp4", dur=8, size="1920x1080")
    sm.smoke(tmp_path / "w", config.Config(), clip=src, backend=Fake())
    out = tmp_path / "w" / "rec" / "out"
    info = media.probe_video(out / "aroll.mp4")
    assert (info["width"], info["height"]) == (1080, 1920) and info["duration"] == pytest.approx(5.0, abs=0.1)
    assert _load(tmp_path / "w", "work/aligned_words.json") == [{"seg": "S1", "word": "Cześć", "start": 0.2, "end": 0.6}]


def test_smoke_music_src(tmp_path, calls):
    bed = tmp_path / "bed.wav"
    bed.write_bytes(b"x")
    sm.smoke(tmp_path / "w", config.Config(), music_src=bed)
    assert _load(tmp_path / "w", "plan.json")["music"] == {"src": str(bed.resolve()), "volume": 0.45}


def test_smoke_rerun_wipes(tmp_path, calls):
    sm.smoke(tmp_path, config.Config())
    stale = tmp_path / "rec" / "out" / "stale.txt"
    stale.write_text("x")
    sm.smoke(tmp_path, config.Config())
    assert not stale.exists()


@pytest.mark.hf
def test_smoke_real_render(tmp_path):
    r = sm.smoke(tmp_path, config.Config())
    info = media.probe_video(r["final"])
    assert r["ok"] and (info["width"], info["height"]) == (1080, 1920)
    assert info["duration"] == pytest.approx(5.0, abs=0.3) and r["frame"].exists()


def test_smoke_short_clip(tmp_path, calls):
    src = make_clip(tmp_path / "in.mp4", dur=3, size="1920x1080")
    sm.smoke(tmp_path / "w", config.Config(), clip=src)
    seg = _load(tmp_path / "w", "work/edl_timed.json")[0]
    assert seg["end"] == pytest.approx(3.0, abs=0.05)
    assert _load(tmp_path / "w", "work/aligned_words.json")[-1]["end"] <= 3.0


def test_smoke_clip_too_short(tmp_path, calls):
    from cutmate.errors import CutmateError
    src = make_clip(tmp_path / "in.mp4", dur=1.5, size="1920x1080")
    with pytest.raises(CutmateError, match="clip too short"):
        sm.smoke(tmp_path / "w", config.Config(), clip=src)
