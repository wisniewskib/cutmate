import json

import pytest
from PIL import Image

from conftest import make_clip
from cutmate.media import extract_frame, probe_video
from cutmate.preview import plate_image, preview

WORDS = [{"seg": "S1", "word": "Cześć", "start": 0.2, "end": 0.6},
         {"seg": "S2", "word": "Dalej", "start": 2.2, "end": 2.6}]
TIMED = [{"id": "S1", "start": 0.0, "end": 2.0, "text": "a"}, {"id": "S2", "start": 2.0, "end": 4.0, "text": "b"}]


def make_out(tmp_path, plan):
    out = tmp_path / "rec" / "out"
    (out / "work").mkdir(parents=True)
    make_clip(out / "aroll.mp4", dur=4.0, size="1920x1080", gaps=())
    (out / "work" / "aligned_words.json").write_text(json.dumps(WORDS, ensure_ascii=False), encoding="utf-8")
    (out / "work" / "edl_timed.json").write_text(json.dumps(TIMED), encoding="utf-8")
    (out / "edl.json").write_text(json.dumps({"format": "16:9", "segments": []}), encoding="utf-8")
    (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return out


def _mean(png):
    im = Image.open(png).convert("L")
    return sum(im.get_flattened_data()) / (im.width * im.height)


def test_preview_with_plate(tmp_path):
    out = make_out(tmp_path, {"chapters": [{"at": "S1:Cześć", "title": "Intro"},
                                           {"at": "S2:Dalej", "title": "Drugi „rozdział” <b>"}]})
    r = preview(out)
    info = probe_video(r["preview"])
    assert (info["width"], info["height"]) == (854, 480) and info["duration"] == pytest.approx(4.0, abs=0.15)
    assert r["chapters"].read_text(encoding="utf-8") == "00:00 Intro\n00:02 Drugi „rozdział” <b>\n"
    assert _mean(extract_frame(r["preview"], 2.8, tmp_path / "plate.png")) < 40      # dark plate
    assert _mean(extract_frame(r["preview"], 1.0, tmp_path / "plain.png")) > 60      # test pattern


def test_preview_without_chapters(tmp_path):
    out = make_out(tmp_path, {})
    (out / "chapters.txt").write_text("stale", encoding="utf-8")
    r = preview(out)
    assert r["chapters"] is None and not (out / "chapters.txt").exists() and r["preview"].exists()


def test_plate_image_size():
    assert plate_image("ROZDZIAŁ 02", "Tytuł ąę", (854, 480), "clean").size == (854, 480)


def test_preview_skips_plate_near_end(tmp_path):
    words = WORDS + [{"seg": "S2", "word": "Koniec", "start": 3.8, "end": 3.95}]
    out = make_out(tmp_path, {"chapters": [{"at": "S1:Cześć", "title": "A"}, {"at": "S2:Koniec", "title": "B"}]})
    (out / "work" / "aligned_words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    r = preview(out)
    assert _mean(extract_frame(r["preview"], 3.9, tmp_path / "late.png")) > 60       # no plate this close to the end


def test_preview_916_with_panel_and_scene(tmp_path):
    """A 9:16 plan with a persistent panel and a scene previews (the cut only — panel items are not drawn here)."""
    out = make_out(tmp_path, {})
    make_clip(out / "aroll.mp4", dur=4.0, size="1080x1920", gaps=())
    (out / "edl.json").write_text(json.dumps({"format": "9:16", "segments": []}), encoding="utf-8")
    (out.parent / "broll").mkdir()
    Image.new("RGB", (32, 18), "blue").save(out.parent / "broll" / "p.png")
    (out / "plan.json").write_text(json.dumps({
        "panel": [{"at": "S1:Cześć", "media": "broll/p.png"}, {"at": "S2:Dalej", "media": "broll/p.png"}],
        "scenes": [{"from": 1.0, "to": 2.1, "media": "broll/p.png"}]}), encoding="utf-8")
    r = preview(out)
    info = probe_video(r["preview"])
    assert (info["width"], info["height"]) == (480, 854) and r["chapters"] is None
