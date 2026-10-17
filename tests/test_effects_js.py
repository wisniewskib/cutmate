import json
import subprocess

from cutmate.paths import plugin_root, web_dir

JS = """
global.window = {};
require(%s);
const F = window.CutmateFX.pure;
const r1 = F.seed(7), r2 = F.seed(7), r3 = F.seed(8);
const a = [r1(), r1(), r1()], b = [r2(), r2(), r2()];
const tr = [[0, 100, 200], [0.4, 300, 400]];
const gap = [[0, 100, 200], [0.2, 100, 200], [1.0, 300, 400], [1.2, 300, 400]];
console.log(JSON.stringify({
  same: JSON.stringify(a) === JSON.stringify(b), diff: r3() !== a[0], range: a.every(v => v >= 0 && v < 1),
  mid: F.trackAt(tr, 0.2), before: F.trackAt(tr, -0.2), after: F.trackAt(tr, 0.6), empty: F.trackAt([], 0.3),
  farBefore: F.trackAt(tr, -1), farAfter: F.trackAt(tr, 9), inGap: F.trackAt(gap, 0.6), gapEdge: F.trackAt(gap, 1.1),
  p1: F.particleState(3, 1.25, {count: 10, seed: 4, life: 1, speed: 100, spin: 2, emitter: (t) => [0, 0]}),
  p2: F.particleState(3, 1.25, {count: 10, seed: 4, life: 1, speed: 100, spin: 2, emitter: (t) => [0, 0]}),
  pn: F.particleState(0, 1.0, {count: 1, seed: 1, life: 1, emitter: () => null}),
}));
"""


def test_pure_helpers():
    path = json.dumps(str(web_dir() / "effects.js"))
    r = subprocess.run(["node", "-e", JS % path], capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    assert d["same"] and d["diff"] and d["range"]
    assert d["mid"] == [200, 300] and d["before"] == [100, 200] and d["after"] == [300, 400] and d["empty"] is None
    assert d["farBefore"] is None and d["farAfter"] is None                  # > 0.25 s outside the samples
    assert d["inGap"] is None and d["gapEdge"] == [300, 400]                 # samples > 0.5 s apart: no position
    assert d["pn"]["alpha"] == 0                                  # null emitter: invisible, no throw
    assert d["p1"] == d["p2"] and 0 <= d["p1"]["alpha"] <= 1      # stateless: same t → same particle


def test_bloom_alpha_option():
    js = (web_dir() / "effects.js").read_text(encoding="utf-8")
    assert 'const keep = opt.bloom.alpha === "keep";' in js
    # "keep": save the clean render before the bloom, merge after it (never a black frame); "luma": brightness alpha
    assert js.index("new SavePass()") < js.index("new UnrealBloomPass") < js.index("tBase") < js.index("new OutputPass()")
    show = (plugin_root() / "themes" / "clean" / "components" / "custom" / "showcase-3d.html").read_text(encoding="utf-8")
    assert "SavePass" not in show and 'alpha: "keep"' in show                 # uses the shared fix


def test_showcase_rests_on_a_low_gesture_spot():
    """Palm held out low in the frame ("tutaj" + open hand): the object sits on the spot instead of covering the hand."""
    show = (plugin_root() / "themes" / "clean" / "components" / "custom" / "showcase-3d.html").read_text(encoding="utf-8")
    lift = show.index("else if (P.place && py > P.h * 0.55) py -= sz.y * scale / UPX / 2;")
    assert show.index("let py = tp ? tp[1] : P.place") < lift < show.index("py = Math.min(P.h - my")    # before the frame clamp


def test_gesture_effects_follow_the_palm_track():
    """An open palm ("tutaj" + presenting hand): burst / showcase-3d / energy-ball ride with P.track over their span."""
    fx = plugin_root() / "themes" / "clean" / "components" / "custom"
    show = (fx / "showcase-3d.html").read_text(encoding="utf-8")
    assert "U.trackAt(P.track, t)" in show and "if (tp) py -= hPx * 0.55;" in show       # rests on the palm
    assert "home0.clone().add(off(t))" in show                                         # home moves with the hand
    burst = (fx / "burst.html").read_text(encoding="utf-8")
    assert "U.trackAt(P.track, t)" in burst and "core.position.copy(S.toWorld(p[0], p[1]))" in burst
    assert "U.trackAt(P.track, t)" in (fx / "energy-ball.html").read_text(encoding="utf-8")


def test_showcase_entry_is_soft_and_burst_is_big():
    fx = plugin_root() / "themes" / "clean" / "components" / "custom"
    show = (fx / "showcase-3d.html").read_text(encoding="utf-8")
    assert "bloom.strength = 0.7 * (0.2 + 0.8 * settle)" in show and "(0.25 + 0.75 * settle)" in show
    burst = (fx / "burst.html").read_text(encoding="utf-8")
    assert "const LEN = Math.max(0.9, Math.min(1.4, P.end - P.at));" in burst                 # ~1 s, not 0.6
    assert "const N = 120;" in burst and "const RINGS = [" in burst and "flares" in burst


READY = """
global.window = {};
require(%s);
const U = window.CutmateFX.make({ to() {} }, {}, "c1", { dur: 1 });
const log = [];
let open;
const p1 = new Promise((r) => { open = r; }).then(() => log.push("p1"));
const back = U.ready(p1);
U.ready(Promise.resolve().then(() => log.push("p2")));
window.__hf.buildReady.c1.then(() => { log.push("ready"); console.log(JSON.stringify({ log, same: back === p1 })); });
Promise.resolve().then(() => Promise.resolve()).then(() => { log.push("tick"); open(); });
"""


def test_ready_extends_build_ready():
    path = json.dumps(str(web_dir() / "effects.js"))
    r = subprocess.run(["node", "-e", READY % path], capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    assert d["same"] and d["log"][-1] == "ready" and {"p1", "p2", "tick"} <= set(d["log"])
    assert d["log"].index("p1") < d["log"].index("ready")                  # waits for every registered promise
