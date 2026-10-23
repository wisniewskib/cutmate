"""Review Focus 2 (no GPU: a Windows laptop renders WebGL in SwiftShader): every WOW effect, 3 s in its main mode (the
first of its index.json `modes`; exploded-view and globe also as a full-frame 9:16 scene, their heaviest placement), is
rendered with `render --no-browser-gpu` on one worker, and so is the same project without it (the same A-roll and
theme, no graphics: the baseline). The cost of one frame WITH the effect is

    s/frame = baseline / frames + (render - baseline) / effect frames

(a plain frame — browser start and encode spread over the whole render — plus the effect's extra time over only the
frames it covers). Each case prints `<case>: <s/frame>` and must stay within BUDGET_S_PER_FRAME. Machine load moves both
renders; run with `uptime` load < 8."""
import json
import shutil
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import wowkit  # noqa: E402
from test_wow_hf import FACE, _hand_tracks, _speaker, _theme, home  # noqa: E402,F401  (home: the CUTMATE_HOME fixture)

from cutmate import paths  # noqa: E402
from cutmate.hf import hf  # noqa: E402
from cutmate.media import run  # noqa: E402

pytestmark = pytest.mark.hf

BUDGET_S_PER_FRAME = 1.5        # s per frame, software GL (plan: Global Constraints, render budget)
FPS = 30
DUR = 4.0                       # the test A-roll (its words run to 4.0 s); every effect spans 0.5–3.5 s
SPAN = {"from": 0.5, "to": 3.5}

CASES = {  # case -> (effect, plan, split-panel theme?)
    "exploded-view": ("exploded-view", {"panel": [{"at": 0.5, "until": 3.5, "effect": "exploded-view",
                                                   "params": {"preset": "engine"}}]}, True),
    "exploded-view-scene": ("exploded-view", {"scenes": [dict(SPAN, effect="exploded-view",
                                                              params={"preset": "phone", "title": "Telefon"})]}, False),
    "globe": ("globe", {"panel": [{"at": 0.5, "until": 3.5, "effect": "globe",
                                   "params": {"from": "PL", "to": ["US", "JP", "BR"]}}]}, True),
    "globe-scene": ("globe", {"scenes": [dict(SPAN, effect="globe", params={"from": "PL", "to": ["US", "JP", "BR"]})]},
                    False),
    "burst-out": ("burst-out", {"face": {"S1": [FACE[0] / 1080, FACE[1] / 1920]},
                                "graphics": [{"type": "bg", **SPAN, "effect": "burst-out", "hit": "S1:mniej",
                                              "params": {"label": "Gotowe!"}}]}, False),
    "hand-control": ("hand-control", {"graphics": [{"type": "custom", "name": "hand-control", **SPAN,
                                                    "params": {"card": {"title": "Kontrola gestem",
                                                                        "lines": ["iskry z palców", "karta z dłoni"]}}}]},
                     False),
    "topic-change": ("topic-change", {"graphics": [{"type": "custom", "name": "topic-change", "from": 2.1, "to": 3.9,
                                                    "params": {"title": "Druga sprawa: koszty"}}]}, False),
    "kinetic-word": ("kinetic-word", {"scenes": [dict(SPAN, effect="kinetic-word", params={"text": "+300%"})]}, True),
}


def _main_mode(effect: str) -> str:
    entries = json.loads((paths.theme_dir("clean") / "components" / "custom" / "index.json").read_text(encoding="utf-8"))
    return next(e for e in entries if e["name"] == effect)["modes"][0]


def _placement(plan: dict) -> str:
    if "scenes" in plan:
        return "scene"
    if "panel" in plan:
        return "panel"
    return plan["graphics"][0]["type"]


def _render(proj: Path) -> float:
    """Wall-clock seconds of a software-GL render of `proj`; fails unless it succeeded in SwiftShader."""
    t0 = time.monotonic()
    r = run(hf("render", "--no-browser-gpu", "--workers", "1", "--quality", "draft", "--fps", str(FPS),
               "-o", "budget.mp4"), cwd=proj)
    took = time.monotonic() - t0
    log = r.stdout + r.stderr
    assert r.returncode == 0, " ".join(log.split())[-1500:]
    assert (Path(proj) / "budget.mp4").stat().st_size > 0
    assert "swiftshader" in log.lower(), "the render did not run in software GL (SwiftShader)"
    return took


_BASE: dict = {}                                    # (theme, A-roll kind) -> baseline render seconds


@pytest.mark.parametrize("case", list(CASES))
def test_wow_render_budget(case, tmp_path, home, monkeypatch):
    from cutmate import build as B
    effect, plan, split = CASES[case]
    theme = _theme(home, "wowbudget") if split else "clean"
    aroll, tracks = None, None
    if effect == "burst-out":                       # the speaker's cut-out is build-time work: a ready one stands in
        aroll, cut, _, _ = _speaker(tmp_path, dur=DUR)

        def fake_cut(src, a, b, media):
            name = f"bgcut-{int(a * 1000)}-{int(b * 1000)}.webm"
            shutil.copyfile(cut, media / name)
            return name
        monkeypatch.setattr(B, "bg_cutout", fake_cut)
    if effect == "hand-control":
        tracks = _hand_tracks(DUR)
    key = (split, effect == "burst-out")
    if key not in _BASE:
        base_proj = wowkit.project(tmp_path / "base", {"graphics": []}, dur=DUR, theme=theme, aroll=aroll)
        _BASE[key] = _render(base_proj)
    proj = wowkit.project(tmp_path, plan, dur=DUR, theme=theme, tracks=tracks, aroll=aroll)
    frames = round(wowkit.duration(proj) * FPS)
    span = plan.get("scenes", plan.get("panel", plan.get("graphics")))[0]
    a = float(span.get("from", span.get("at")))
    b = float(span.get("to", span.get("until")))
    fx_frames = round((b - a) * FPS)
    took = _render(proj)
    base = _BASE[key]
    s_per_frame = base / frames + max(0.0, took - base) / fx_frames
    print(f"{case}: {s_per_frame:.3f} s/frame (render {took:.1f} s, baseline {base:.1f} s, {fx_frames} of {frames} "
          f"frames with the effect; {_placement(plan)}, main mode {_main_mode(effect)})")
    assert s_per_frame <= BUDGET_S_PER_FRAME, f"{case}: {s_per_frame:.3f} s/frame > {BUDGET_S_PER_FRAME}"
