import re
from pathlib import Path

import pytest

from cutmate import effects, paths
from cutmate.build import _sections
from cutmate.plan import TYPES

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
