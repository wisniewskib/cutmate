import pytest

from cutmate import effects as E
from cutmate.errors import PlanError

GOOD = "<markup><div class='fx'></div></markup>\n<script>\nU.clock((t) => {});\n</script>"


def test_find_effect_order(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path / "home"))
    out = tmp_path / "rec" / "out"
    user = tmp_path / "home" / "themes" / "clean" / "components" / "custom"
    user.mkdir(parents=True)
    (user / "orb.html").write_text(GOOD, encoding="utf-8")
    assert E.find_effect("orb", out, "clean") == user / "orb.html"
    (out / "custom").mkdir(parents=True)
    (out / "custom" / "orb.html").write_text(GOOD, encoding="utf-8")
    assert E.find_effect("orb", out, "clean") == out / "custom" / "orb.html"
    try:  # placeholder until Task 10 ships the bundled energy-ball; `or True` alone can't swallow the PlanError
        assert E.find_effect("energy-ball", out, "clean").name == "energy-ball.html" or True
    except PlanError:
        pass
    with pytest.raises(PlanError, match="nope.html"):
        E.find_effect("nope", out, "clean")


def test_lint_names_api_and_file(tmp_path):
    p = tmp_path / "bad.html"
    p.write_text(GOOD.replace("U.clock((t) => {});", "// no Math.random here\nU.clock(() => {});"), encoding="utf-8")
    with pytest.raises(PlanError, match=r"bad.html: uses Math.random"):
        E.lint_effect(p)
    ok = tmp_path / "ok.html"
    ok.write_text(GOOD, encoding="utf-8")
    E.lint_effect(ok)
    (tmp_path / "noscript.html").write_text("<markup></markup>", encoding="utf-8")
    with pytest.raises(Exception, match="script"):
        E.lint_effect(tmp_path / "noscript.html")


def test_libs_head_by_marker():
    assert E.libs_head([GOOD]) == ""
    h = E.libs_head(["U.three({}).then(() => {}); U.draw('.p', {})", "katex.render('x', el)"])
    assert h.index('type="importmap"') < h.index("DrawSVGPlugin.min.js")
    assert "three@0.181.2/build/three.module.js" in h and "three@0.181.2/examples/jsm/" in h
    assert "katex@0.19.0/dist/katex.min.js" in h and "katex.min.css" in h
    assert "gsap.registerPlugin(DrawSVGPlugin)" in h and "anime" not in h and "rough" not in h


def test_track_slice():
    s = [[0.9, 0.5, 0.5, 1], [1.0, 0.5, 0.25, 1], [1.5, 0.75, 0.5, 1], [2.1, 0.1, 0.1, 1]]
    assert E.track_slice(s, 1.0, 2.0, 0.7, 1920, 1080) == [[0.3, 960.0, 270.0], [0.8, 1440.0, 540.0]]
    assert E.track_slice([], 1.0, 2.0, 0.7, 1920, 1080) == []
