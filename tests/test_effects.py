import json
import re

import pytest

from cutmate import effects as E
from cutmate.errors import CutmateError, PlanError
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
    assert "three@0.181.2/build/three.module.min.js" in h and "three@0.181.2/examples/jsm/" in h
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
        assert e["kind"] in ("explainer", "vfx", "3d", "wow")
        assert isinstance(e["description"], str) and e["description"]
        assert isinstance(e["params"], dict) and all(isinstance(v, str) for v in e["params"].values())
        assert isinstance(e["follow"], bool) and isinstance(e["place"], bool)


def test_iso_machine_lint_and_index(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path / "home"))
    p = E.find_effect("iso-machine", tmp_path / "out", "clean")
    assert p == BUNDLED / "iso-machine.html"
    E.lint_effect(p)
    idx = {e["name"]: e for e in json.loads((BUNDLED / "index.json").read_text(encoding="utf-8"))}
    assert idx["iso-machine"]["kind"] == "explainer"
    assert {"parts", "token", "counter", "title"} <= set(idx["iso-machine"]["params"])


@pytest.mark.parametrize("name,kind,params", [
    ("energy-ball", "3d", {"radius", "colors"}),
    ("showcase-3d", "3d", {"shape", "text", "model", "color", "x", "y"}),
    ("burst", "vfx", {"colors", "x", "y"}),
    ("hand-sparks", "vfx", {"mode", "colors", "size", "link"}),
])
def test_vfx_lint_and_index(tmp_path, monkeypatch, name, kind, params):
    import json
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path / "home"))
    p = E.find_effect(name, tmp_path / "out", "clean")
    assert p == BUNDLED / f"{name}.html"
    E.lint_effect(p)
    idx = {e["name"]: e for e in json.loads((BUNDLED / "index.json").read_text(encoding="utf-8"))}
    assert idx[name]["kind"] == kind
    assert params <= set(idx[name]["params"])
    assert idx[name]["follow"] is (name in ("energy-ball", "hand-sparks"))
    assert idx[name]["place"] is True                                          # energy-ball too (without follow)


def test_ui_mock_post_counters_only_from_params():
    import json
    idx = {e["name"]: e for e in json.loads((BUNDLED / "index.json").read_text(encoding="utf-8"))}
    assert {"replies", "reposts", "likes"} <= set(idx["ui-mock"]["params"])
    js = (BUNDLED / "ui-mock.html").read_text(encoding="utf-8")
    assert "P.replies" in js and "P.likes" in js and "U.seed" not in js       # no invented numbers


def _css_rule(html, sel):
    import re
    m = re.search(r"ROOT " + re.escape(sel) + r" \{([^}]*)\}", html)
    return m.group(1) if m else ""


def test_stat_card_media_is_a_readable_framed_screenshot():
    import re
    html = (BUNDLED / "stat-card.html").read_text(encoding="utf-8")
    shot = _css_rule(html, ".sc-shot")
    assert shot and "brightness" not in shot and "blur" not in shot          # the framed shot itself is not dimmed
    bg = re.search(r"brightness\(([\d.]+)\)", _css_rule(html, ".sc-bg"))
    assert bg and float(bg.group(1)) >= 0.4                                  # the ambient copy behind is lighter too
    assert '"sc-shot"' in html and "P.media" in html


def test_ui_mock_window_fits_its_content():
    html = (BUNDLED / "ui-mock.html").read_text(encoding="utf-8")
    fit = html[html.index("const fit = () =>"):html.index("fit();")]
    # after the font size is picked, the window shrinks to head + finished feed (+ footer) and is centred in the panel
    assert "head.offsetHeight" in fit and "feed.offsetHeight" in fit
    assert "Object.assign(win.style, { top: (P.h - h) / 2" in fit and 'height: h + "px"' in fit


def test_iso_machine_labels_anchor_on_their_own_part():
    html = (BUNDLED / "iso-machine.html").read_text(encoding="utf-8")
    assert "BY - 0.04, BW / 2 + 0.12" not in html                           # not the belt edge in front of the part
    for shape in ("box", "cylinder", "funnel", "screen", "gear"):
        assert shape + ":" in html[html.index("const ANCHOR"):html.index("const ANCHOR") + 900], shape


def test_held_slice_holds_nearest_sample():
    """Gesture-placed effects stay on the last seen hand position instead of vanishing (and start without waiting)."""
    from cutmate.effects import held_slice
    s = [[0.5, 0.5, 0.5, 1.0], [0.6, 0.5, 0.5, 1.0], [2.0, 0.6, 0.5, 1.0]]
    out = held_slice(s, 1.0, 2.5, 1.0, 100, 100)
    assert out[0] == [0.0, 50.0, 50.0]                                  # before the window: nearest earlier sample
    assert all(b[0] - a[0] <= 0.5 for a, b in zip(out, out[1:]))        # no gap that trackAt would blank
    assert out[-1] == [1.5, 60.0, 50.0] and [1.0, 60.0, 50.0] in out
    assert held_slice([], 0, 1, 0, 100, 100) == []


ALL_MARKS = ("U.three({}) U.post({}) anime.stagger U.anime( lottie.load U.lottie( katex.render U.tex( rough.svg U.rough( d3.select "
             "drawSVG morphSVG motionPath SplitText")


def test_libs_head_is_local():
    head = E.libs_head([ALL_MARKS])
    assert "http" not in head and "assets/vendor/" in head
    for folder in E.VENDOR.values():
        assert f"assets/vendor/{folder}/" in head or folder.startswith("gsap@")
    imap = json.loads(re.search(r'<script type="importmap">(.*?)</script>', head).group(1))["imports"]
    # "./": an import map address that is a bare "assets/..." is ignored by the browser ("Bare specifier")
    assert imap == {"three": "./assets/vendor/three@0.181.2/build/three.module.min.js",
                    "three/addons/": "./assets/vendor/three@0.181.2/examples/jsm/",
                    "postprocessing": "./assets/vendor/postprocessing@6.39.5/build/index.js"}
    only3 = json.loads(re.search(r'<script type="importmap">(.*?)</script>', E.libs_head(["U.three({})"])).group(1))["imports"]
    assert "postprocessing" not in only3 and set(only3) == {"three", "three/addons/"}
    quoted = E.libs_head(["await import('postprocessing')"])                     # postprocessing implies three
    assert '"three"' in quoted and '"postprocessing"' in quoted
    assert "importmap" not in E.libs_head(["gsap.to(x)"])


def test_vendor_files_selects_used():
    assert E.vendor_files([]) == ["gsap@3.14.2"] and E.vendor_files(["x"]) == ["gsap@3.14.2"]
    assert E.vendor_files(["U.three({})"]) == ["gsap@3.14.2", "three@0.181.2"]
    assert E.vendor_files(["U.post({})"]) == ["gsap@3.14.2", "three@0.181.2", "postprocessing@6.39.5"]
    assert E.vendor_files(["U.tex('x')", "d3.select()"]) == ["gsap@3.14.2", "katex@0.19.0", "d3@7.9.0"]
    assert set(E.vendor_files([ALL_MARKS])) == set(E.VENDOR.values())


def test_vendor_root_falls_back_to_home_then_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(E, "vendor_dir", lambda: tmp_path / "bundled")
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path / "home"))
    with pytest.raises(CutmateError, match=r'gsap@3.14.2 not found.*run "\$CM" vendor \(or /cutmate:setup\)'):
        E.vendor_root("gsap@3.14.2")
    (tmp_path / "home" / "vendor" / "gsap@3.14.2").mkdir(parents=True)
    assert E.vendor_root("gsap@3.14.2") == tmp_path / "home" / "vendor" / "gsap@3.14.2"
    (tmp_path / "bundled" / "gsap@3.14.2").mkdir(parents=True)
    assert E.vendor_root("gsap@3.14.2") == tmp_path / "bundled" / "gsap@3.14.2"


def test_effect_meta(tmp_path):
    fx = tmp_path / "custom" / "kinetic-word.html"
    fx.parent.mkdir()
    fx.write_text(GOOD, encoding="utf-8")
    assert E.effect_meta(fx) == {}                                          # no index.json
    index = fx.parent / "index.json"
    entry = {"name": "kinetic-word", "kind": "wow", "modes": ["scene", "overlay"], "webgl": False,
             "aroll_fx": {"dur": 0.6}, "params": {"text": "the word"}}
    index.write_text(json.dumps([{"name": "other", "kind": "3d"}, "junk", entry], ensure_ascii=False), encoding="utf-8")
    assert E.effect_meta(fx) == entry
    assert E.effect_meta(fx.with_name("globe.html")) == {}                  # no entry for this stem
    index.write_text("[{broken", encoding="utf-8")
    assert E.effect_meta(fx) == {}
    index.write_text(json.dumps({"name": "kinetic-word"}), encoding="utf-8")   # not a list
    assert E.effect_meta(fx) == {}
    index.write_bytes(b"\xff\xfe\x00junk")                                   # not UTF-8
    assert E.effect_meta(fx) == {}
    stock = plugin_root() / "themes" / "clean" / "components" / "custom" / "energy-ball.html"
    assert E.effect_meta(stock)["name"] == "energy-ball" and "kind" in E.effect_meta(stock)


@pytest.mark.parametrize("api", ["onComplete", "onRepeat", "onRender", "onBegin", "onLoop", ".restart(", "GlitchEffect",
                                 "ScrambleTextPlugin", "onStart", "onReverseComplete", "onBeforeUpdate"])
def test_new_forbidden_apis(tmp_path, api):
    assert api in E.FORBIDDEN
    p = tmp_path / "wow.html"
    p.write_text(GOOD.replace("U.clock((t) => {});", f"x.{api.strip('.(')}({{}});" if api == ".restart(" else f"// {api}\nU.clock(() => {{}});"),
                 encoding="utf-8")
    with pytest.raises(PlanError, match=re.escape(f"wow.html: uses {api}")):
        E.lint_effect(p)


def test_every_repo_effect_passes_the_extended_lint():
    """Every stock effect / component script in the repo still lints with the extended FORBIDDEN list."""
    root = plugin_root()
    files = [p for p in root.rglob("*.html") if not ({".venv", "node_modules", "vendor", ".git"} & set(p.parts))
             and "<script>" in p.read_text(encoding="utf-8")]
    assert len(files) > 20
    hits = [(p.relative_to(root).as_posix(), api) for p in files for api in E.FORBIDDEN
            if api in dict(E._SECTION.findall(p.read_text(encoding="utf-8"))).get("script", "")]
    assert hits == []


def test_tip_slice_keeps_ext_and_drops_long_gaps():
    """Fingertips: like held_slice (starts at a, px, local t) but each sample keeps its extended flag, and a finger that
    is not seen any more is held at most 0.25 s, then marked not extended (no sparks from a missing finger)."""
    from cutmate.effects import tip_slice
    s = [[1.0, 0.5, 0.5, 1.0], [1.1, 0.52, 0.5, 1.0], [1.2, 0.54, 0.5, 0.0], [2.0, 0.6, 0.4, 1.0]]
    out = tip_slice(s, 0.9, 2.5, 0.5, 1000, 1000)
    assert out[0] == [0.4, 500.0, 500.0, 1.0]                            # starts at a with the nearest sample (0.1 s away)
    assert [0.6, 520.0, 500.0, 1.0] in out and [0.7, 540.0, 500.0, 0.0] in out
    assert [0.95, 540.0, 500.0, 0.0] in out                              # 0.25 s after the last sight: off
    assert [1.5, 600.0, 400.0, 1.0] in out
    assert out[-1] == [1.75, 600.0, 400.0, 0.0]                          # gone 0.25 s after the track ends (b = 2.5)
    assert all(b[0] >= a[0] for a, b in zip(out, out[1:]))
    s2 = [[1.0, 0.5, 0.5, 1.0], [1.1, 0.52, 0.5, 1.0]]
    far = tip_slice(s2, 0.2, 1.15, 0.0, 100, 100)
    assert far[0] == [0.2, 50.0, 50.0, 0.0]                              # nearest sample 0.8 s away: not held, off
    assert tip_slice([], 0, 1, 0, 100, 100) == []
    px = tip_slice(s2, 1.0, 1.1, 1.0, 100, 100, lambda x, y, t: (x * 10, y * 20))
    assert px[0] == [0.0, 5.0, 10.0, 1.0]
