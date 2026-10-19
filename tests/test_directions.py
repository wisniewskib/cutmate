import colorsys
import json

import pytest
from PIL import Image

from cutmate import build, directions
from cutmate.effects import THEME_RE
from cutmate.errors import CutmateError
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


def _hl(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    hh, l, _ = colorsys.rgb_to_hls(r, g, b)
    return hh * 360, l


def test_palettes_readable():
    assert len(directions.PALETTES) >= 10 and len(directions.FONT_PAIRS) >= 10
    for p in directions.PALETTES:
        assert directions.contrast(p["ink"], p["card"]) >= 4.5, p["name"]
        assert directions.contrast(p["on_accent"], p["accent"]) >= 4.5, p["name"]
        assert directions.contrast(p["accent"], p["card"]) >= 3.0, p["name"]
        assert p["accent"] != "#7dd3fc"
    c = directions.CLEAN["palette"]
    assert directions.contrast(c["on_accent"], c["accent"]) >= 4.5
    assert directions.contrast("#000000", "#ffffff") == pytest.approx(21)


def test_palettes_distinct_and_balanced():
    """Any two accents differ by >= 25 degrees of hue OR by >= 0.2 HSL lightness."""
    ps = directions.PALETTES
    for i, a in enumerate(ps):
        for b in ps[:i]:
            (h1, l1), (h2, l2) = _hl(a["accent"]), _hl(b["accent"])
            dh = abs(h1 - h2)
            dh = min(dh, 360 - dh)
            assert dh >= 25 or abs(l1 - l2) >= 0.2, (a["name"], b["name"])
    light = sum(_hl(p["card"])[1] > 0.5 for p in ps)
    assert abs(light - (len(ps) - light)) <= 1
    assert "mono" not in {p["name"] for p in ps}


def test_font_pairs_varied():
    fp = directions.FONT_PAIRS
    assert all(d != t for d, t in fp)
    assert sum(t == "Inter" for _, t in fp) <= 1
    assert sum(d in {"Anton", "Bebas Neue", "Oswald", "Big Shoulders Display"} for d, _ in fp) <= 2
    assert {"Space Mono", "Caveat", "Titan One"} & {d for d, _ in fp}


def test_roll_exhausted_avoid_raises(monkeypatch):
    monkeypatch.setattr(directions, "SHAPES", {"sharp": "x"})
    with pytest.raises(CutmateError, match="drop some --avoid"):
        directions.roll(3, avoid=[{"shapes": "sharp"}])


def test_roll_relaxes_to_most_recent_avoid():
    every_shape = [{"shapes": s} for s in directions.SHAPES]  # strict avoid is impossible
    r = directions.roll(3, avoid=every_shape)
    assert r["shapes"] != every_shape[-1]["shapes"]


def test_suggest_name_matches_theme_re():
    for s in range(50):
        d = directions.roll(s)
        assert THEME_RE.match(directions.suggest_name(d, set()))


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
