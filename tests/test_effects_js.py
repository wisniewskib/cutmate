import json
import subprocess

from cutmate.paths import web_dir

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
    assert d["p1"] == d["p2"] and 0 <= d["p1"]["alpha"] <= 1      # stateless: same t → same particle


def test_bloom_alpha_option():
    js = (web_dir() / "effects.js").read_text(encoding="utf-8")
    assert '(opt.bloom.alpha || "luma") !== "keep"' in js
    assert js.index('!== "keep"') < js.index("ShaderPass.js")             # the luma pass is skipped for "keep"
