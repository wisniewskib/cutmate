import json

import pytest
from PIL import Image

from cutmate import build, directions
from cutmate.paths import plugin_root


def test_roll_is_deterministic():
    assert directions.roll(7) == directions.roll(7)
    a, b = directions.roll(7), directions.roll(8)
    assert any(a[k] != b[k] for k in ("palette", "fonts", "shapes", "motion"))


def test_roll_never_clean():
    for s in range(200):
        r = directions.roll(s)
        assert r["fonts"]["display"] != "Inter"
        assert r["shapes"] != "rounded"
        assert r["motion"] != "bouncy"
        assert r["palette"]["name"] != "clean"
        assert r["palette"]["accent"] != "#7dd3fc"


def test_roll_avoid_differs_in_font_shapes_motion():
    a = directions.roll(1)
    b = directions.roll(1, avoid=[a])
    assert b["fonts"]["display"] != a["fonts"]["display"]
    assert b["shapes"] != a["shapes"]
    assert b["motion"] != a["motion"]
    assert b["palette"]["name"] != a["palette"]["name"]


def test_palettes_readable():
    assert len(directions.PALETTES) >= 10 and len(directions.FONT_PAIRS) >= 10
    for p in directions.PALETTES:
        assert directions.contrast(p["ink"], p["card"]) >= 4.5, p["name"]
        assert p["accent"] != "#7dd3fc"
    assert directions.contrast("#000000", "#ffffff") == pytest.approx(21)


def test_suggest_name_unique():
    d = {"palette": {"name": "acid"}, "shapes": "brutal"}
    assert directions.suggest_name(d, set()) == "acid-brutal"
    assert directions.suggest_name(d, {"acid-brutal"}) == "acid-brutal-2"


def test_palette_of_two_colours(tmp_path):
    im = Image.new("RGB", (40, 20), "#ff0000")
    im.paste(Image.new("RGB", (20, 20), "#0000ff"), (20, 0))
    f = tmp_path / "a.png"
    im.save(f)
    got = directions.palette_of([f], n=2)
    assert {h for h, _ in got} == {"#ff0000", "#0000ff"}
    assert all(s == pytest.approx(0.5, abs=0.05) for _, s in got)


def test_clean_theme_has_bundled_direction():
    th = plugin_root() / "themes" / "clean"
    assert json.loads((th / "theme.json").read_text(encoding="utf-8"))["direction"] == directions.CLEAN
    assert build._theme_meta(th)["direction"]["mode"] == "bundled"
