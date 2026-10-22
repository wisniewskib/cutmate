import json
import re
import subprocess

import pytest

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
// settled: fully opaque and at rest (no entrance offset / scale left) along the whole parent chain
const settled = (e) => { let op = 1; for (let x = e; x; x = x.parentNode) { const s = x.style;
  if (s.display === "none" || s.visibility === "hidden") return false;
  if (s.opacity !== undefined && s.opacity !== "") op *= Number(s.opacity);
  for (const [, fn, args] of String(s.transform || "").matchAll(/(\w+)\(([^)]*)\)/g)) {
    const v = args.split(",").map(parseFloat);
    if (/^translate/.test(fn) && v.some((a) => Math.abs(a) > 1.5)) return false;
    if (/^scale/.test(fn) && v.some((a) => Math.abs(a - 1) > 0.03)) return false;
  } }
  return op >= 0.99; };
const out = {};
for (const [k, t, sel, what] of %(probes)s) {
  seek(t);
  out[k] = root.querySelectorAll(sel).map((e) => (what === "on" ? e.classList.contains("on") : what === "text" ? e.textContent
    : what === "settled" ? settled(e) : what === "kids" ? e.children.map(settled) : shown(e)));
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
    # 4 s item: the rows tick in over [1.05, 1.5] (U.fullAt = at + 0.5), one every 0.1125 s
    d = _run_effect("checklist", P, [["mid", 1.2, ".ck-row", "shown"], ["sum", 4.8, ".ck-sum-v", "text"],
                                     ["start", 1.04, ".ck-row", "shown"]])
    assert d["mid"] == [True, True, False, False]
    assert d["start"] == [False, False, False, False]
    assert d["sum"] == ["50%"]


PANEL = """
global.window = {};
require(%s);
const mkEl = () => ({ style: {}, children: [], appendChild(c) { this.children.push(c); c.parent = this; return c; },
                      remove() { this.parent.children = this.parent.children.filter((x) => x !== this); } });
global.document = { createElement: mkEl };
const root = mkEl();
const out = {};
for (const [k, color] of [["light", "rgb(239, 236, 231)"], ["dark", "rgb(11, 11, 15)"], ["none", ""], ["mid", "rgb(160, 160, 160)"]]) {
  let probe = null;
  global.getComputedStyle = (e) => { probe = e; return { color }; };
  const U = window.CutmateFX.make({ to() {} }, root, "c1", { dur: 1 });
  out[k] = U.panelLight(root);
  out[k + "Var"] = probe.style.color;
}
out.left = root.children.length;
console.log(JSON.stringify(out));
"""


def test_panel_light_reads_the_panel_colour():
    path = json.dumps(str(web_dir() / "effects.js"))
    r = subprocess.run(["node", "-e", PANEL % path], capture_output=True, text=True, encoding="utf-8", check=True)
    d = json.loads(r.stdout)
    assert d["light"] is True and d["dark"] is False and d["none"] is False and d["mid"] is True
    assert d["lightVar"] == "var(--panel-bg, #0b0b0f)"        # the theme token, clean's colour as the fallback
    assert d["left"] == 0                                       # the probe element is removed again


# Fill speed: on a 1-2 s panel item the card / structure and its content are readable at once — every explainer's
# build-in is done by min(0.6 s, 40 % of the item span); later beats (count-up, toggles, strike, tokens) may continue.
SPANS = [1.0, 1.5, 2.0, 5.0]


def _at40(span):
    return round(1.0 + 0.4 * span, 4)


def _p(span, **kw):
    return dict(kw, lang="pl", at=1.0, end=1.0 + span, w=1000, h=820, dur=1.0 + span + 0.5)


def test_full_at_is_inside_the_0_6_s_40_percent_budget():
    js = "global.window = {}; require(%s); const U = window.CutmateFX.make({ to() {} }, {}, 'c1', { dur: 1 });" \
         "console.log(JSON.stringify([U.fullAt(1, 2), U.fullAt(1, 2.5), U.fullAt(1, 6), U.fullAt(1, 1)]));"
    r = subprocess.run(["node", "-e", js % json.dumps(str(web_dir() / "effects.js"))], capture_output=True, text=True,
                       check=True)
    assert json.loads(r.stdout) == [1.35, 1.5, 1.5, 1]           # min(0.5 s, 35 %): a frame of margin


@pytest.mark.parametrize("span", SPANS)
@pytest.mark.parametrize("mode, kicker", [("type", None), ("pop", None), ("type", "AUTOR")])
def test_headline_is_whole_at_40_percent(span, mode, kicker):
    P = _p(span, text="Pół roku później", mode=mode, **({"kicker": kicker} if kicker else {}))
    t = _at40(span)
    d = _run_effect("headline", P, [["box", t, ".hl", "settled"], ["text", t, ".hl-text", "text"],
                                    ["words", t, ".w", "settled"], ["kick", t, ".hl-kick", "settled"]])
    assert d["box"] == [True] and d["text"] == ["Pół roku później"] and all(d["words"]) and all(d["kick"])


@pytest.mark.parametrize("span", SPANS)
@pytest.mark.parametrize("layout", ["card", "hero"])
def test_stat_card_is_whole_at_40_percent(span, layout):
    P = _p(span, value=75, prefix="-", suffix="%", label="tokenów zużytych mniej", note="źródło: README", layout=layout)
    t = _at40(span)
    d = _run_effect("stat-card", P, [["card", t, ".sc-card", "settled"], ["label", t, ".sc-label", "kids"],
                                     ["note", t, ".sc-note", "settled"]])
    assert d["card"] == [True] and d["label"] == [[True] * 3] and d["note"] == [True]


@pytest.mark.parametrize("span", SPANS)
def test_checklist_is_whole_at_40_percent(span):
    rows = [{"text": t, "status": st} for t, st in [("Płacisz", "bad"), ("Gorsze odpowiedzi", "bad"),
                                                    ("Mniej tokenów", "ok"), ("Kontekst", "warn")]]
    P = _p(span, title="Caveman", rows=rows, strike=True, summary={"value": 75, "suffix": "%", "label": "drożej"})
    t = _at40(span)
    d = _run_effect("checklist", P, [["card", t, ".ck-card", "settled"], ["rows", t, ".ck-row", "settled"],
                                     ["pills", t, ".ck-pill", "text"]])
    assert d["card"] == [True] and d["rows"] == [True] * 4
    assert "···" not in d["pills"], d["pills"]                     # every status has landed


@pytest.mark.parametrize("span", SPANS)
def test_flow_is_whole_at_40_percent(span):
    P = _p(span, title="Co Claude czyta", nodes=["Prompt", "Kontekst", "Pliki", "Odpowiedź"])
    t = _at40(span)
    d = _run_effect("flow", P, [["title", t, ".fl-title", "settled"], ["nodes", t, ".fl-node", "settled"]])
    assert d["title"] == [True] and d["nodes"] == [True] * 4


LINES = [{"who": "user", "text": "Zrób mi stronę"}, {"who": "ai", "text": "Jasne, oto strona."}]


@pytest.mark.parametrize("span", SPANS)
@pytest.mark.parametrize("kind", ["chat", "post", "terminal"])
def test_ui_mock_feed_is_whole_at_40_percent(span, kind):
    P = _p(span, kind=kind, lines=LINES, title="Autor")
    t = _at40(span)
    d = _run_effect("ui-mock", P, [["win", t, ".um-win", "settled"], ["msgs", t, ".msg", "settled"],
                                   ["text", t, ".msg", "text"]])
    assert d["win"] == [True]
    assert d["msgs"][:2] == [True, True]
    assert d["text"][0].endswith("Zrób mi stronę") and d["text"][1].endswith("Jasne, oto strona.")


@pytest.mark.parametrize("span", SPANS)
@pytest.mark.parametrize("kind", ["browser", "app"])
def test_ui_mock_page_is_whole_at_40_percent(span, kind):
    rows = [{"text": f"Row {i}", "toggle": i == 1, "click": i == 1} for i in range(4)]
    P = _p(span, kind=kind, title="Connectors", url="github.com/x/y", search="fire", rows=rows, highlight=1)
    t = _at40(span)
    d = _run_effect("ui-mock", P, [["win", t, ".um-win", "settled"], ["rows", t, ".um-row", "settled"],
                                   ["search", t, ".um-search", "text"]])
    assert d["win"] == [True] and d["rows"] == [True] * 4 and "fire" in d["search"][0]


def test_iso_machine_build_in_is_scaled_to_the_span():
    """iso-machine (three.js, not runnable here): every build-in time goes through tB() / kB, which squeeze the natural
    1.35 s assembly into U.fullAt — no raw `P.at + <number>` start left except the conveyor's indexing start."""
    from cutmate.build import _sections
    script = _sections(plugin_root() / "themes" / "clean" / "components" / "custom" / "iso-machine.html")["script"]
    assert "const kB = Math.min(1, (U.fullAt(P.at, P.end) - P.at) / BUILD);" in script
    assert "const BUILD = 1.35;" in script and "const tB = (x) => P.at + x * kB;" in script
    raw = re.findall(r"P\.at \+ [^\n;]*", script)
    assert raw == ["P.at + x * kB", "P.at + Math.min(1.0, span * 0.3)"], raw     # tB() itself and the conveyor start
    assert len(re.findall(r"\b(?:const|let|var)\s+tB\b|\btB\s*=[^=>]", script)) == 1   # never shadowed (the crate has a T)
    assert "dur: (dur || 0.36) * kB" in script and "(0.4 * kB)" in script and "(0.35 * kB)" in script
