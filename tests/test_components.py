import pytest

from cutmate import paths
from cutmate.build import _sections
from cutmate.plan import TYPES

EXTRA = ("chapter",)
PENDING = ("side",)  # components arrive in Tasks 6 and 7 — remove each when its file exists


def test_every_component_has_a_script_and_no_forbidden_apis():
    d = paths.theme_dir("clean") / "components"
    # custom effects live in custom/ folders, not as theme components
    for t in [t for t in TYPES if t not in ("custom",) + PENDING] + list(EXTRA):
        sec = _sections(d / f"{t}.html")
        js = sec["script"]
        for bad in ("Date.now", "Math.random", "performance.now", "onUpdate", "setTimeout", ".play("):
            assert bad not in js, f"{t}: {bad}"
        assert "tl." in js, t


def test_split_uses_media_tag():
    sec = _sections(paths.theme_dir("clean") / "components" / "split.html")
    assert "{{media_tag}}" in sec["markup"]


@pytest.mark.hf
@pytest.mark.parametrize("fmt, n", [("9:16", 9), ("16:9", 11)])
def test_theme_check_clean(tmp_path, fmt, n):
    from PIL import Image
    from cutmate.theme_check import theme_check
    r = theme_check("clean", tmp_path, fmt=fmt)
    assert r["sheet"].exists() and len(r["snapshots"]) == n
    w, h = Image.open(r["snapshots"][0]).size
    assert (w > h) == (fmt == "16:9")


def test_theme_css_has_169_layout():
    css = (paths.theme_dir("clean") / "theme.css").read_text(encoding="utf-8")
    for sel in ("html.f169 .band", "html.f169 #captions", "html.f169 .cw", "html.f169 .card .big",
                "html.f169 .ttl .title", "html.f169 .stamp", "html.f169 .chip", "html.f169 .list .item",
                "html.f169 .bars"):
        assert sel in css, sel
    md = (paths.theme_dir("clean") / "frame.md").read_text(encoding="utf-8")
    assert "## 16:9" in md and "1340" in md and "pip" in md and "lower-third" in md
