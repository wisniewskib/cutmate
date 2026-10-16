import re

import pytest

from cutmate import effects as E
from cutmate.errors import PlanError
from cutmate.paths import plugin_root

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
    assert E.find_effect("energy-ball", out, "clean") == \
        plugin_root() / "themes" / "clean" / "components" / "custom" / "energy-ball.html"
    with pytest.raises(PlanError, match="nope.html"):
        E.find_effect("nope", out, "clean")


def test_bundled_energy_ball_passes_lint(tmp_path):
    E.lint_effect(E.find_effect("energy-ball", tmp_path, "clean"))


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


def test_save_effect_force_and_bundled_untouched(tmp_path, monkeypatch):
    import json
    from cutmate.effects import save_effect
    from cutmate.errors import CutmateError
    from cutmate.paths import plugin_root
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path / "home"))
    out = tmp_path / "rec" / "out"
    (out / "custom").mkdir(parents=True)
    (out / "custom" / "orb.html").write_text(GOOD, encoding="utf-8")
    (out / "plan.json").write_text(json.dumps({"graphics": [
        {"type": "custom", "name": "orb", "at": "S1:a", "follow": "hand", "params": {"color": "#fff", "size": 2}}]}))
    bundled = sorted(p.name for p in (plugin_root() / "themes" / "clean").rglob("*"))
    p = save_effect(out, "orb", "clean", "Kula energii na dłoni")
    assert p == tmp_path / "home" / "themes" / "clean" / "components" / "custom" / "orb.html"
    idx = json.loads((p.parent / "index.json").read_text(encoding="utf-8"))
    assert idx == [{"name": "orb", "description": "Kula energii na dłoni", "params": ["color", "size"], "follow": "hand"}]
    with pytest.raises(CutmateError, match="--force"):
        save_effect(out, "orb", "clean")
    save_effect(out, "orb", "clean", "v2", force=True)
    assert [e["description"] for e in json.loads((p.parent / "index.json").read_text())] == ["v2"]
    (out / "custom" / "unused.html").write_text(GOOD, encoding="utf-8")
    save_effect(out, "unused", "clean")
    assert {"name": "unused", "description": "", "params": [], "follow": None} in json.loads((p.parent / "index.json").read_text())
    assert sorted(p.name for p in (plugin_root() / "themes" / "clean").rglob("*")) == bundled


def test_find_effect_falls_back_to_bundled_clean(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path / "home"))
    assert E.find_effect("energy-ball", tmp_path / "out", "mytheme") == \
        plugin_root() / "themes" / "clean" / "components" / "custom" / "energy-ball.html"
    with pytest.raises(PlanError) as e:
        E.find_effect("nope", tmp_path / "out", "mytheme")
    assert str(plugin_root() / "themes" / "clean" / "components" / "custom" / "nope.html") in str(e.value)


@pytest.mark.parametrize("name, theme, msg", [("../evil", "clean", "effect name"), ("Orb", "clean", "effect name"),
                                              ("orb", "../x", "theme name"), ("orb", "a/b", "theme name")])
def test_save_effect_validates_names(tmp_path, monkeypatch, name, theme, msg):
    from cutmate.errors import CutmateError
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path / "home"))
    with pytest.raises(CutmateError, match=msg):
        E.save_effect(tmp_path / "out", name, theme)


@pytest.mark.parametrize("which", ["plan.json", "index.json"])
def test_save_effect_corrupt_json_is_one_line_error(tmp_path, monkeypatch, which):
    from cutmate.errors import CutmateError
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path / "home"))
    out = tmp_path / "rec" / "out"
    (out / "custom").mkdir(parents=True)
    (out / "custom" / "orb.html").write_text(GOOD, encoding="utf-8")
    idx = tmp_path / "home" / "themes" / "clean" / "components" / "custom" / "index.json"
    idx.parent.mkdir(parents=True)
    (out / "plan.json" if which == "plan.json" else idx).write_text("{oops", encoding="utf-8")
    with pytest.raises(CutmateError, match=which) as e:
        E.save_effect(out, "orb", "clean")
    assert "\n" not in str(e.value)


@pytest.mark.parametrize("api", ["THREE.Clock", "new Date", "crypto.getRandomValues", "gsap.ticker", ".play("])
def test_lint_rejects_clock_and_playback_apis(tmp_path, api):
    p = tmp_path / "fx.html"
    p.write_text(GOOD.replace("U.clock((t) => {});", f"const x = {api}; U.clock(() => {{}});"), encoding="utf-8")
    with pytest.raises(PlanError, match=re.escape(f"fx.html: uses {api}")):
        E.lint_effect(p)


def test_save_effect_copies_assets_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path / "home"))
    out = tmp_path / "rec" / "out"
    (out / "custom" / "orb").mkdir(parents=True)
    (out / "custom" / "orb.html").write_text(GOOD, encoding="utf-8")
    (out / "custom" / "orb" / "anim.json").write_text("{}", encoding="utf-8")
    p = E.save_effect(out, "orb", "clean")
    assert (p.parent / "orb" / "anim.json").exists()
    (out / "custom" / "orb" / "anim.json").unlink()
    (out / "custom" / "orb" / "new.json").write_text("{}", encoding="utf-8")
    E.save_effect(out, "orb", "clean", force=True)
    assert sorted(f.name for f in (p.parent / "orb").iterdir()) == ["new.json"]


BUNDLED = plugin_root() / "themes" / "clean" / "components" / "custom"


@pytest.mark.parametrize("name", ["stat-card", "flow", "ui-mock"])
def test_bundled_explainers_lint(tmp_path, monkeypatch, name):
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path / "home"))
    p = E.find_effect(name, tmp_path / "out", "clean")
    assert p == BUNDLED / f"{name}.html"
    E.lint_effect(p)


def test_bundled_index_json():
    import json
    idx = json.loads((BUNDLED / "index.json").read_text(encoding="utf-8"))
    assert isinstance(idx, list) and idx
    names = [e["name"] for e in idx]
    assert len(names) == len(set(names))
    assert sorted(names) == sorted(p.stem for p in BUNDLED.glob("*.html"))
    for e in idx:
        assert set(e) >= {"name", "kind", "description", "params", "follow", "place"}, e["name"]
        assert e["kind"] in ("explainer", "vfx", "3d")
        assert isinstance(e["description"], str) and e["description"]
        assert isinstance(e["params"], dict) and all(isinstance(v, str) for v in e["params"].values())
        assert isinstance(e["follow"], bool) and isinstance(e["place"], bool)
