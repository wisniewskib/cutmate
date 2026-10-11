import json

import pytest

from cutmate import media
from cutmate.cut import cut_aroll, load_edl
from cutmate.errors import EDLError
from conftest import make_clip


def write_edl(rec, segments, fmt="9:16"):
    out = rec / "out"
    out.mkdir(parents=True, exist_ok=True)
    p = out / "edl.json"
    p.write_text(json.dumps({"format": fmt, "fps": 30, "segments": segments}, ensure_ascii=False), encoding="utf-8")
    return p


SEGS = [{"id": "S1", "file": "take1.mp4", "in": 0.0, "out": 1.0, "text": "raz"},
        {"id": "S2", "file": "take1.mp4", "in": 1.5, "out": 3.0, "text": "dwa"}]


def check_aroll(edl, w=1080, h=1920):
    timed = cut_aroll(edl)
    out = edl.parent
    info = media.probe_video(out / "aroll.mp4")
    assert (info["width"], info["height"], info["fps"]) == (w, h, "30/1")
    assert info["duration"] == pytest.approx(2.5, abs=0.1)
    assert media.integrated_lufs(out / "aroll.mp4") == pytest.approx(-14, abs=1.0)
    assert [s["start"] for s in timed] == pytest.approx([0.0, 1.0], abs=0.04)
    saved = json.loads((out / "work" / "edl_timed.json").read_text(encoding="utf-8"))
    assert saved[1]["end"] == pytest.approx(2.5, abs=0.05) and "gain_db" in saved[0]
    return timed


def test_cut_basic(tmp_path):
    rec = tmp_path / "rec"
    make_clip(rec / "take1.mp4")
    check_aroll(write_edl(rec, SEGS))


def test_cut_unicode_path(tmp_path):
    rec = tmp_path / "źródła" / "nagranie 1 ąę"
    make_clip(rec / "take1.mp4")
    check_aroll(write_edl(rec, SEGS))


def test_cut_mixed_resolutions(tmp_path):
    rec = tmp_path / "rec"
    make_clip(rec / "take1.mp4", size="1080x1920")
    make_clip(rec / "wide.mp4", size="1280x720")
    segs = [SEGS[0], {"id": "S2", "file": "wide.mp4", "in": 1.5, "out": 3.0, "text": "dwa"}]
    check_aroll(write_edl(rec, segs))


def test_cut_16x9(tmp_path):
    rec = tmp_path / "rec"
    make_clip(rec / "take1.mp4", size="1920x1080")
    check_aroll(write_edl(rec, SEGS, fmt="16:9"), w=1920, h=1080)


@pytest.mark.parametrize("seg,msg", [
    ({"id": "X", "file": "missing.mp4", "in": 0, "out": 1, "text": ""}, "not found"),
    ({"id": "X", "file": "take1.mp4", "in": 2, "out": 1, "text": ""}, "after in"),
    ({"id": "X", "file": "take1.mp4", "in": 0, "out": 9, "text": ""}, "longer than"),
    ({"id": "X", "file": "silent.mp4", "in": 0, "out": 1, "text": ""}, "no audio"),
    ({"id": "X", "file": "take1.mp4", "in": 0, "text": ""}, "missing.*out"),
    ({"id": "X", "in": 0, "out": 1, "text": ""}, "needs.*file"),
    ({"id": "X", "file": "take1.mp4", "in": "a", "out": 1, "text": ""}, "numbers"),
])
def test_edl_validation(tmp_path, seg, msg):
    rec = tmp_path / "rec"
    make_clip(rec / "take1.mp4")
    make_clip(rec / "silent.mp4", audio=False)
    with pytest.raises(EDLError, match=msg) as e:
        load_edl(write_edl(rec, [seg]))
    assert "\n" not in str(e.value)


def test_edl_empty(tmp_path):
    with pytest.raises(EDLError, match="no segments"):
        load_edl(write_edl(tmp_path / "rec", []))


def test_edl_invalid_json(tmp_path):
    p = tmp_path / "edl.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(EDLError, match="not valid JSON") as e:
        load_edl(p)
    assert "\n" not in str(e.value)


def test_edl_missing_file(tmp_path):
    with pytest.raises(EDLError, match="not found"):
        load_edl(tmp_path / "nope.json")
