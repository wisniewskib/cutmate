"""Review Focus 2 (no GPU: a Windows laptop renders WebGL in SwiftShader): every WOW effect, 3 s in its main mode (the
first of its index.json `modes`; exploded-view and globe also as a full-frame 9:16 scene, their heaviest placement), is
rendered with `render --no-browser-gpu` on one worker. Each prints `<effect>: <s/frame>` and must stay within
BUDGET_S_PER_FRAME. The time is the whole render's wall clock (browser start, the 1 s of plain A-roll around the effect
and the encode included) over the project's frames: an upper bound on the effect's own cost."""
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
    proj = wowkit.project(tmp_path, plan, dur=DUR, theme=theme, tracks=tracks, aroll=aroll)
    frames = round(wowkit.duration(proj) * FPS)
    t0 = time.monotonic()
    r = run(hf("render", "--no-browser-gpu", "--workers", "1", "--quality", "draft", "--fps", str(FPS),
               "-o", "budget.mp4"), cwd=proj)
    took = time.monotonic() - t0
    s_per_frame = took / frames
    print(f"{case}: {s_per_frame:.3f} s/frame ({took:.1f} s for {frames} frames, main mode {_main_mode(effect)})")
    assert r.returncode == 0, " ".join((r.stdout + r.stderr).split())[-1500:]
    assert (Path(proj) / "budget.mp4").stat().st_size > 0
    assert s_per_frame <= BUDGET_S_PER_FRAME, f"{case}: {s_per_frame:.3f} s/frame > {BUDGET_S_PER_FRAME}"
