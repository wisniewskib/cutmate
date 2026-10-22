import re
from pathlib import Path

import pytest

from cutmate import effects, paths
from cutmate.build import _sections
from cutmate.plan import TYPES

SPLIT_PANEL_SNAPSHOTS = 35   # the split-panel theme check sample: panel item / scene mids + LOOK + settled tiles

EXTRA = ("chapter",)
PENDING = ()  # components arrive in Tasks 6 and 7 — remove each when its file exists


def test_every_component_has_a_script_and_no_forbidden_apis():
    d = paths.theme_dir("clean") / "components"
    # custom effects live in custom/ folders, not as theme components
    for t in [t for t in TYPES if t not in ("custom",) + PENDING] + list(EXTRA):
        sec = _sections(d / f"{t}.html")
        js = sec["script"]
        for bad in effects.FORBIDDEN:
            assert bad not in js, f"{t}: {bad}"
        assert "tl." in js, t


def test_split_uses_media_tag():
    sec = _sections(paths.theme_dir("clean") / "components" / "split.html")
    assert "{{media_tag}}" in sec["markup"]


@pytest.mark.hf
@pytest.mark.parametrize("fmt, n", [("9:16", 25), ("16:9", 29)])
def test_theme_check_clean(tmp_path, fmt, n):
    from PIL import Image
    from cutmate.theme_check import theme_check
    r = theme_check("clean", tmp_path, fmt=fmt)
    assert r["sheet"].exists() and len(r["snapshots"]) == n and len(r["labels"]) == n
    w, h = Image.open(r["snapshots"][0]).size
    assert (w > h) == (fmt == "16:9")


@pytest.mark.hf
def test_theme_check_old_theme_169(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from test_build import _old_theme
    from cutmate.theme_check import theme_check
    monkeypatch.setenv("CUTMATE_HOME", str(tmp_path / "home"))
    _old_theme(tmp_path / "home")
    r = theme_check("old", tmp_path / "work", fmt="16:9")
    assert r["sheet"].exists() and len(r["snapshots"]) == 29


def test_theme_css_is_frame_only():
    css = (paths.theme_dir("clean") / "theme.css").read_text(encoding="utf-8")
    selectors = " ".join(re.findall(r"([^{}]+)\{", re.sub(r"/\*.*?\*/", "", css, flags=re.S)))
    for part in (".bg-", ".side-", ".ttl", ".card", ".stamp", ".chip", ".list", ".bars", ".point", ".split-", ".chapter",
                 ".lt", ".pip-"):
        assert part not in selectors, part
    for sel in ("#captions", ".cw", ".band", "html.f169 #captions", "html.f169 .cw", "html.f169 .band"):
        assert sel in css, sel
    md = (paths.theme_dir("clean") / "frame.md").read_text(encoding="utf-8")
    assert "## 16:9" in md and "1340" in md and "pip" in md and "lower-third" in md


@pytest.mark.parametrize("comp, sel", [
    ("bg", "ROOT .bg-wrap"), ("side", "ROOT .side-panel.side-l"), ("pip", "ROOT .pip-face"),
    ("split", "ROOT .split-edge"), ("chapter", "html.f169 ROOT .chapter .ch-title"), ("lower-third", "ROOT .lt"),
    ("counter", "html.f169 ROOT .card .big"), ("title", "html.f169 ROOT .ttl .title"),
    ("stamp", "html.f169 ROOT .stamp"), ("chip", "html.f169 ROOT .chip"), ("list", "html.f169 ROOT .list .item"),
    ("bars", "html.f169 ROOT .bars"), ("point", "html.f169 ROOT .point"),
])
def test_components_carry_their_css(comp, sel):
    assert sel in _sections(paths.theme_dir("clean") / "components" / f"{comp}.html")["style"]


def test_components_measure_with_theme_font():
    d = paths.theme_dir("clean")
    assert "Inter" not in (d / "components" / "chip.html").read_text(encoding="utf-8")
    assert 'getPropertyValue("--font")' in (paths.plugin_root() / "core" / "cutmate" / "web" / "effects.js").read_text(encoding="utf-8")


def test_clean_tokens_font_blocks():
    d = paths.theme_dir("clean")
    tokens = (d / "tokens.css").read_text(encoding="utf-8")
    for kind in ("text", "display"):
        assert f"/* cutmate:font {kind} */" in tokens and f"/* /cutmate:font {kind} */" in tokens
    assert "--font-display" in tokens and "--font:" in tokens
    assert (d / "fonts" / "OFL-inter.txt").exists()


def _g(type_, start, end, **params):
    from cutmate.plan import Graphic
    return Graphic(type_, start, end, params, False, None, 0)


def test_snapshot_times_nudge_only_look_clashes():
    from cutmate.theme_check import snapshot_times
    # a split and the custom effect it expands to settle at the same moment: one tile, no near-duplicate at +0.05
    gs = [_g("split", 10.0, 14.0, effect="fx"), _g("custom", 10.0, 14.0, name="fx")]
    cps, labels = snapshot_times(gs, [10.4])
    assert cps == [10.4, 12.0] and labels == [(10.4, "split", "settled"), (12.0, "custom", "mid")]
    # a LOOK component whose settled moment falls on an earlier claim (a custom mid) is nudged, never dropped
    gs = [_g("custom", 0.0, 2.6, name="fx"), _g("chip", 0.9, 3.0, text="x")]
    cps, labels = snapshot_times(gs, [])
    assert labels == [(0.4, "custom", "settled"), (1.0, "chip", "entrance"), (1.3, "custom", "mid"),
                      (1.35, "chip", "settled")]
    assert cps == [t for t, _, _ in labels]


def test_theme_check_after_a_check_deadline_warns_and_snapshots(tmp_path, monkeypatch, capsys):
    """A check cut off by hyperframes' deadline is not a broken theme: warn and go on to the snapshots."""
    from cutmate import theme_check as tc
    from cutmate.hf import DEADLINE_WARN, CheckResult
    monkeypatch.setattr(tc, "check", lambda proj, run, hf: CheckResult("deadline", "did not finish within its deadline"))
    _fake_snapshot_run(monkeypatch, tc)
    r = tc.theme_check("clean", tmp_path, fmt="9:16")
    assert DEADLINE_WARN in capsys.readouterr().out
    assert r["sheet"].exists() and len(r["snapshots"]) == len(r["times"]) > 0


def test_theme_check_real_check_failure_raises(tmp_path, monkeypatch):
    from cutmate import theme_check as tc
    from cutmate.errors import CutmateError
    from cutmate.hf import CheckResult
    monkeypatch.setattr(tc, "check", lambda proj, run, hf: CheckResult("failed", "lint error: x"))
    _fake_snapshot_run(monkeypatch, tc)
    with pytest.raises(CutmateError, match="fails hyperframes check: lint error"):
        tc.theme_check("clean", tmp_path, fmt="9:16")


def _fake_snapshot_run(monkeypatch, tc):
    """ffmpeg runs for real (synthetic media); `hyperframes snapshot` writes one PNG per requested time."""
    from PIL import Image
    real = tc.run

    def run(cmd, cwd=None, env=None):
        if "snapshot" not in cmd:
            return real(cmd, cwd=cwd, env=env)
        times = cmd[cmd.index("--at") + 1].split(",")
        d = Path(cwd) / "snapshots"
        d.mkdir(exist_ok=True)
        for i, _ in enumerate(times):
            Image.new("RGB", (1080, 1920), "#336699").save(d / f"frame-{i:03d}.png")
        import subprocess
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(tc, "run", run)
    monkeypatch.setattr(tc, "build", _fake_build(tc.build))


def _fake_build(real):
    def build(out, **kw):
        from cutmate import build as B
        import unittest.mock as m
        with m.patch.object(B, "ensure_project", lambda proj, fmt="9:16": (proj.mkdir(parents=True, exist_ok=True),
                                                                          (proj / "hyperframes.json").write_text("{}"))):
            return real(out, **kw)
    return build


LAYOUT_COMPONENTS = ("panel", "panel-media", "scene")


def test_layout_components_scripted():
    d = paths.theme_dir("clean") / "components"
    for t in LAYOUT_COMPONENTS:
        sec = _sections(d / f"{t}.html")
        assert "tl." in sec["script"], t
        for bad in effects.FORBIDDEN:
            assert bad not in sec["script"], f"{t}: {bad}"
    panel = (d / "panel.html").read_text(encoding="utf-8")
    assert "var(--panel-bg" in panel and "var(--accent)" in panel
    assert "P.open_at_zero" in panel and "P.stays" in panel
    assert "{{media_tag}}" in _sections(d / "panel-media.html")["markup"]
    assert "{{media_tag}}" in _sections(d / "scene.html")["markup"]


def test_lint_checks_layout_components_when_present(tmp_path):
    import shutil
    from cutmate.themes import lint_theme
    dst = tmp_path / "t"
    shutil.copytree(paths.theme_dir("clean"), dst)
    assert not [p for p in lint_theme(dst, "t") if p.startswith(LAYOUT_COMPONENTS)]
    (dst / "components" / "panel.html").write_text("<style></style><markup><div></div></markup><script>\nconst a = 1;\n"
                                                   "</script>", encoding="utf-8")
    (dst / "components" / "scene.html").write_text("<markup><div></div></markup>", encoding="utf-8")
    (dst / "components" / "panel-media.html").write_text("<script>tl.set(root, {}, 0); Math.random();</script>",
                                                         encoding="utf-8")
    probs = lint_theme(dst, "t")
    assert "panel: script never uses tl. (no timeline animation)" in probs
    assert "scene: no <script> section" in probs
    assert "panel-media: uses Math.random (not allowed)" in probs
    for t in LAYOUT_COMPONENTS:
        (dst / "components" / f"{t}.html").unlink()
    assert not [p for p in lint_theme(dst, "t") if p.startswith(LAYOUT_COMPONENTS)]     # optional: absent is fine


EXPLAINERS = ("stat-card", "flow", "ui-mock", "iso-machine", "checklist", "headline")


def _custom_dir() -> Path:
    return paths.theme_dir("clean") / "components" / "custom"


def test_explainers_use_theme_tokens():
    for name in EXPLAINERS:
        text = (_custom_dir() / f"{name}.html").read_text(encoding="utf-8")
        assert "var(--panel-bg" in text and "var(--font-display)" in text, name
        assert "#0b0b0f" not in re.sub(r"var\([^)]*\)", "", text), name


def test_index_json_documents_new_params():
    import json
    idx = {e["name"]: e for e in json.loads((_custom_dir() / "index.json").read_text(encoding="utf-8"))}
    for name in ("checklist", "headline"):
        assert idx[name]["kind"] == "explainer", name
    ui = json.dumps(idx["ui-mock"]["params"], ensure_ascii=False)
    assert "browser" in ui and "app" in ui
    assert "layout" in idx["stat-card"]["params"]


def test_new_templates_lint():
    for name in ("checklist", "headline"):
        effects.lint_effect(_custom_dir() / f"{name}.html")


@pytest.mark.hf
def test_explainers_take_theme_look(tmp_path, monkeypatch):
    """A theme with a light panel colour: checklist, ui-mock app and stat-card hero all paint the panel in it."""
    import json
    import shutil
    import sys
    from PIL import Image
    sys.path.insert(0, str(Path(__file__).parent))
    from conftest import make_clip
    from test_build import TIMED, WORDS
    from cutmate import build as B
    from cutmate.hf import check, hf
    from cutmate.media import run
    home = tmp_path / "home"
    dst = home / "themes" / "lightpanel"
    shutil.copytree(paths.theme_dir("clean"), dst)
    tokens = (dst / "tokens.css").read_text(encoding="utf-8")
    tokens = tokens.replace("--panel-bg: #0b0b0f;", "--panel-bg: #efece7;").replace("--accent: #7dd3fc;", "--accent: #c2501f;")
    assert "#efece7" in tokens and "#c2501f" in tokens
    (dst / "tokens.css").write_text(tokens, encoding="utf-8")
    monkeypatch.setenv("CUTMATE_HOME", str(home))
    o = tmp_path / "rec" / "out"
    (o / "work").mkdir(parents=True)
    make_clip(o / "aroll.mp4", dur=4.0, gaps=())
    (o / "work" / "aligned_words.json").write_text(json.dumps(WORDS, ensure_ascii=False), encoding="utf-8")
    (o / "work" / "edl_timed.json").write_text(json.dumps(TIMED), encoding="utf-8")
    plan = {"panel": [
        {"at": 0.1, "effect": "checklist", "params": {"title": "Link check", "summary": {"value": 50, "suffix": "%"}, "rows": [
            {"text": "example.com/a", "status": "ok", "label": "200 OK"},
            {"text": "example.com/b", "status": "bad", "label": "404"}]}},
        {"at": "S1:mniej", "effect": "ui-mock", "params": {"kind": "app", "title": "Connectors", "search": "fire", "rows": [
            {"text": "Alpha", "toggle": False}, {"text": "Beta", "toggle": True, "click": True}]}},
        {"at": "S2:minus", "effect": "stat-card", "params": {"layout": "hero", "value": 50, "suffix": "%", "label": "X"}}]}
    (o / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    proj = B.build(o, theme="lightpanel")["project"]
    chk = check(proj)
    assert chk.status in ("ok", "deadline"), chk.output[-3000:]
    for at in ("0.6", "1.7", "3.0"):
        d = f"snap-{at}"
        snap = run(hf("snapshot", "--at", at, "--no-end", "--describe", "false", "-o", d), cwd=proj)
        assert snap.returncode == 0, (snap.stdout + snap.stderr)[-2000:]
        shot = sorted((proj / d).glob("*.png"))[0]
        img = Image.open(shot).convert("RGB")
        w, h = img.size
        px = img.getpixel((round(60 * w / 1080), round(60 * h / 1920)))
        print(f"snapshot {at}: {shot} corner={px}")
        assert all(abs(c - e) <= 6 for c, e in zip(px, (0xef, 0xec, 0xe7))), (at, shot, px)


def test_synthetic_split_panel_plan(tmp_path):
    import json
    from cutmate.layout import SPLIT_DEFAULTS
    from cutmate.plan import load_plan
    from cutmate.theme_check import _synthetic_rec
    out = _synthetic_rec(tmp_path, "9:16", None, SPLIT_DEFAULTS)
    raw = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert not [g for g in raw["graphics"] if g["type"] == "split"]
    assert len(raw["panel"]) == 9 and len(raw["scenes"]) == 1
    assert (out.parent / "broll" / "page.png").exists() and (out.parent / "broll" / "clip.mp4").exists()
    plan = load_plan(out, layout=SPLIT_DEFAULTS)
    assert not [w for w in plan.warnings if "WARN panel gap" in w] and plan.panel["open_at_zero"]
    # classic 9:16 and 16:9 keep the old plan
    out2 = _synthetic_rec(tmp_path / "c", "9:16", None, None)
    assert "panel" not in json.loads((out2 / "plan.json").read_text(encoding="utf-8"))


def test_snapshot_times_include_panel_mids():
    from cutmate.theme_check import snapshot_times
    gs = [_g("panel-media", 2.0, 4.0, media="a.png", _panel=True), _g("panel-media", 4.0, 6.5, media="b.png", _panel=True),
          _g("scene", 10.0, 12.0, media="a.png", _scene=True)]
    cps, labels = snapshot_times(gs, [])
    assert (3.0, "panel-media", "mid") in labels and (5.25, "panel-media", "mid") in labels
    assert (11.0, "scene", "mid") in labels


@pytest.mark.hf
def test_theme_check_split_panel(tmp_path, monkeypatch):
    import json
    import shutil
    from PIL import Image
    from cutmate.layout import SPLIT_DEFAULTS
    from cutmate.plan import load_plan
    from cutmate.theme_check import theme_check
    theme = tmp_path / "split"
    shutil.copytree(paths.theme_dir("clean"), theme)
    meta = json.loads((theme / "theme.json").read_text(encoding="utf-8"))
    meta["layout"] = {"mode": "split-panel"}
    (theme / "theme.json").write_text(json.dumps(meta), encoding="utf-8")
    r = theme_check(str(theme), tmp_path / "w", fmt="9:16", layout=SPLIT_DEFAULTS)
    from cutmate import themes
    out = r["sheet"].parent
    plan = load_plan(out, layout=SPLIT_DEFAULTS)
    layers = [g for g in plan.graphics if g.params.get("_panel") or g.params.get("_scene")]
    assert len(layers) == 10                                  # 9 panel items + 1 scene
    mids = [(t, ty) for t, ty, k in r["labels"] if k == "mid"]
    for g in layers:                                          # every item / scene has its own mid tile
        assert any(g.start <= t <= g.end and ty == g.type for t, ty in mids), (g.type, g.start)
    assert len(r["snapshots"]) == len(r["labels"]) == len(r["times"]) == SPLIT_PANEL_SNAPSHOTS
    assert r["sheet"].exists() and Image.open(r["sheet"]).width == 1350
    contact = tmp_path / "contact.png"
    themes._contact_sheet({"9:16": r, "16:9": r}, contact)    # every LOOK type has its entrance + settled tile
    assert Image.open(contact).width == 1620


def test_split_panel_items_have_a_free_window_and_mid_snapshot(tmp_path):
    from cutmate.layout import SPLIT_DEFAULTS
    from cutmate.plan import load_plan
    from cutmate.theme_check import LOOK, _synthetic_rec, free_window, snapshot_times
    out = _synthetic_rec(tmp_path, "9:16", None, SPLIT_DEFAULTS)
    plan = load_plan(out, layout=SPLIT_DEFAULTS)
    assert not [w for w in plan.warnings if "WARN panel gap" in w]
    cps, labels = snapshot_times(plan.graphics, [])
    items = [g for g in plan.graphics if g.params.get("_panel")]
    assert len(items) == 9
    for g in items:
        w = free_window(g, plan.graphics)
        assert w and w[1] - w[0] >= 1.0, (g.type, g.start, g.end, w)
        mids = [t for t, ty, k in labels if k == "mid" and g.start <= t <= g.end]
        assert any(w[0] <= t <= w[1] for t in mids), (g.start, w, mids)
    assert {ty for _, ty, k in labels if k == "entrance"} == set(LOOK)    # every LOOK type keeps its tile


def test_free_window():
    from cutmate.theme_check import free_window
    item = _g("custom", 0.0, 6.0, _panel=True)
    assert free_window(item, [item]) == (0.0, 6.0)                                       # no band at all
    assert free_window(item, [item, _g("title", -1.0, 2.0)]) == (2.0, 6.0)               # a band covering the start
    assert free_window(item, [item, _g("title", 1.0, 2.0), _g("chip", 4.5, 5.0)]) == (2.0, 4.5)   # bands in the middle
    assert free_window(item, [item, _g("title", 0.0, 6.5)]) is None                      # a band covering it all
    assert free_window(item, [item, _g("scene", 1.0, 5.0, _scene=True)]) == (0.0, 6.0)   # scenes / panel layers are no bands
    assert free_window(item, [item, _g("panel", 0.0, 6.0)]) == (0.0, 6.0)
