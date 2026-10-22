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


# a tiny DOM + timeline stub: runs a stock effect's <script> the way build.py's SUBCOMP does and seeks its U.clock
DOM = r"""
global.window = {};
require(%(fx)s);
class Style { constructor() { this._p = {}; } setProperty(k, v) { this._p[k] = String(v); } getPropertyValue(k) { return this._p[k] || ""; } }
class El {
  constructor(tag) { this.tagName = String(tag).toUpperCase(); this.children = []; this.parentNode = null; this.style = new Style();
    this._cls = new Set(); this._text = ""; this.attrs = {}; this.offsetWidth = 0; this.offsetHeight = 0; this.offsetTop = 0;
    this.offsetLeft = 0; this.clientHeight = 0; this.clientWidth = 0; const self = this;
    this.classList = { add: (...c) => c.forEach((x) => self._cls.add(x)), remove: (...c) => c.forEach((x) => self._cls.delete(x)),
      contains: (c) => self._cls.has(c), toggle: (c, on) => { const v = on === undefined ? !self._cls.has(c) : !!on;
        if (v) self._cls.add(c); else self._cls.delete(c); return v; } }; }
  get className() { return Array.from(this._cls).join(" "); }
  set className(v) { this._cls = new Set(String(v).split(/\s+/).filter(Boolean)); }
  get textContent() { return this.children.length ? this.children.map((c) => c.textContent).join("") : this._text; }
  set textContent(v) { this.children = []; this._text = String(v); }
  set innerHTML(v) { this.children = []; this._html = String(v); }
  get innerHTML() { return this._html || ""; }
  appendChild(c) { if (c.parentNode) c.remove(); c.parentNode = this; this.children.push(c); return c; }
  insertBefore(c, ref) { this.appendChild(c); return c; }
  remove() { if (this.parentNode) { const p = this.parentNode; p.children = p.children.filter((x) => x !== this); this.parentNode = null; } }
  removeChild(c) { c.remove(); return c; }
  setAttribute(k, v) { this.attrs[k] = String(v); } getAttribute(k) { return this.attrs[k]; }
  getBoundingClientRect() { return { left: 0, top: 0, width: 0, height: 0, right: 0, bottom: 0 }; }
  getTotalLength() { return 1; } getPointAtLength() { return { x: 0, y: 0 }; }
  all() { return this.children.reduce((a, c) => a.concat([c], c.all()), []); }
  querySelectorAll(sel) { const c = sel.replace(/^\./, ""); return this.all().filter((e) => e._cls.has(c)); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
}
global.document = { createElement: (t) => new El(t), createElementNS: (ns, t) => new El(t), documentElement: new El("html") };
global.getComputedStyle = () => ({ getPropertyValue: () => "", color: "" });
const updates = [];
const tl = { to(target, vars) { if (vars && vars.onUpdate) updates.push([target, vars]); return tl; },
             set() { return tl; }, fromTo() { return tl; } };
const root = new El("div");
const m = %(markup)s.match(/class="([^"]+)"/);
if (m) root.appendChild(new El("div")).className = m[1];
const P = %(params)s;
const U = Object.assign(window.CutmateFX.make(tl, root, "c1", P), {
  el(tag, cls, text, parent) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; (parent || root).appendChild(e); return e; },
});
%(script)s
const seek = (t) => updates.forEach(([c, v]) => { c.t = t; v.onUpdate(); });
const shown = (e) => { for (let x = e; x; x = x.parentNode) { const s = x.style;
  if (s.display === "none" || s.visibility === "hidden" || (s.opacity !== undefined && s.opacity !== "" && Number(s.opacity) <= 0)) return false; }
  return true; };
const out = {};
for (const [k, t, sel, what] of %(probes)s) {
  seek(t);
  out[k] = root.querySelectorAll(sel).map((e) => (what === "on" ? e.classList.contains("on") : what === "text" ? e.textContent : shown(e)));
}
console.log(JSON.stringify(out));
"""


def _run_effect(name: str, params: dict, probes: list) -> dict:
    from cutmate.build import _sections
    sec = _sections(plugin_root() / "themes" / "clean" / "components" / "custom" / f"{name}.html")
    js = DOM % {"fx": json.dumps(str(web_dir() / "effects.js")), "markup": json.dumps(sec.get("markup", "")),
                "params": json.dumps(params), "script": sec["script"], "probes": json.dumps(probes)}
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_ui_mock_app_flips_toggles():
    P = {"kind": "app", "title": "Connectors", "search": "fire", "lang": "pl", "at": 0.5, "end": 4.5, "w": 1000, "h": 880,
         "dur": 4.5, "rows": [{"text": "Gmail", "toggle": False}, {"text": "Firecrawl", "toggle": True, "click": True},
                              {"text": "Drive", "toggle": False}]}
    d = _run_effect("ui-mock", P, [["early", 0.6, ".um-row", "shown"], ["late", 4.2, ".tg", "on"],
                                   ["rows", 4.2, ".um-row", "shown"], ["before", 1.0, ".tg", "on"]])
    assert d["early"] == [False, False, False]
    assert d["rows"] == [True, True, True]
    assert d["late"] == [False, True, False]
    assert d["before"] == [False, False, False]           # the clicked row starts off and flips on at the click


def test_checklist_rows_tick_in_order():
    rows = [{"text": f"site{i}.com/x", "status": s} for i, s in enumerate(["ok", "bad", "warn", "ok"])]
    P = {"title": "Link check", "rows": rows, "strike": True, "summary": {"value": 50, "suffix": "%"},
         "lang": "en", "at": 1.0, "end": 5.0, "w": 1000, "h": 880, "dur": 5.0}
    d = _run_effect("checklist", P, [["mid", 3.0, ".ck-row", "shown"], ["sum", 4.8, ".ck-sum-v", "text"],
                                     ["start", 1.1, ".ck-row", "shown"]])
    assert d["mid"] == [True, True, False, False]
    assert d["start"] == [False, False, False, False]
    assert d["sum"] == ["50%"]
