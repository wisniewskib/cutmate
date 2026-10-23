import json
import math
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
         "lang": "en", "at": 1.0, "end": 5.0, "w": 1000, "h": 880, "dur": 5.0, "panel": True}
    # 4 s panel item: the rows tick in over [1.05, 1.5] (U.fullAt = at + 0.5), one every 0.1125 s
    d = _run_effect("checklist", P, [["mid", 1.2, ".ck-row", "shown"], ["sum", 4.8, ".ck-sum-v", "text"],
                                     ["start", 1.04, ".ck-row", "shown"]])
    assert d["mid"] == [True, True, False, False]
    assert d["start"] == [False, False, False, False]
    assert d["sum"] == ["50%"]


def test_checklist_classic_keeps_its_natural_pace():
    """Not a panel item (classic split / side): the rows tick in over [P.at + 0.3, P.end - 0.4], as before the
    panel build-in polish."""
    rows = [{"text": f"site{i}.com/x", "status": s} for i, s in enumerate(["ok", "bad", "warn", "ok"])]
    P = {"title": "Link check", "rows": rows, "strike": True, "summary": {"value": 50, "suffix": "%"},
         "lang": "en", "at": 1.0, "end": 5.0, "w": 1000, "h": 880, "dur": 5.0}
    d = _run_effect("checklist", P, [["mid", 3.0, ".ck-row", "shown"], ["sum", 4.8, ".ck-sum-v", "text"],
                                     ["start", 1.1, ".ck-row", "shown"], ["full", 1.5, ".ck-row", "shown"]])
    assert d["mid"] == [True, True, False, False]
    assert d["start"] == [False, False, False, False] and d["full"] == [False, False, False, False]
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


# Fill speed: on a 1-2 s panel item (P.panel, set by build) the card / structure and its content are readable at once —
# every explainer's build-in is done by min(0.6 s, 40 % of the item span); later beats (count-up, toggles, strike,
# tokens) may continue. Classic split / side explainers (no P.panel) keep their natural pace.
SPANS = [1.0, 1.5, 2.0, 5.0]


def _at40(span):
    return round(1.0 + 0.4 * span, 4)


def _p(span, **kw):
    return dict(kw, lang="pl", at=1.0, end=1.0 + span, w=1000, h=820, dur=1.0 + span + 0.5, panel=True)


def _classic(span, **kw):
    P = _p(span, **kw)
    del P["panel"]
    return P


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
    assert "const kB = P.panel ? Math.min(1, (U.fullAt(P.at, P.end) - P.at) / BUILD) : 1;" in script
    assert "const BUILD = 1.35;" in script and "const tB = (x) => P.at + x * kB;" in script
    raw = re.findall(r"P\.at \+ [^\n;]*", script)
    assert raw == ["P.at + x * kB", "P.at + Math.min(1.0, span * 0.3)"], raw     # tB() itself and the conveyor start
    assert len(re.findall(r"\b(?:const|let|var)\s+tB\b|\btB\s*=[^=>]", script)) == 1   # never shadowed (the crate has a T)
    assert "dur: (dur || 0.36) * kB" in script and "(0.4 * kB)" in script and "(0.35 * kB)" in script


def test_classic_explainers_keep_their_natural_pace():
    """A 5 s classic split / side explainer (no P.panel) is still building at the panel's fullAt (1.5 s) and whole
    before its end: ui-mock chat types over ~78 % of the span, headline at ~16 letters / s, flow nodes over the span."""
    t_fast, t_late = 1.5, 1.0 + 5.0 - 0.3                   # U.fullAt(1, 6) = 1.5 / near the end
    d = _run_effect("ui-mock", _classic(5.0, kind="chat", lines=LINES, title="Autor"),
                    [["fast", t_fast, ".msg", "text"], ["late", t_late, ".msg", "text"]])
    assert not d["fast"][1].endswith("Jasne, oto strona.") and d["late"][1].endswith("Jasne, oto strona.")
    d = _run_effect("ui-mock", _p(5.0, kind="chat", lines=LINES, title="Autor"), [["fast", t_fast, ".msg", "text"]])
    assert d["fast"][1].endswith("Jasne, oto strona.")                          # the panel item: whole by fullAt
    P = _classic(5.0, text="Pół roku później", mode="pop")
    d = _run_effect("headline", P, [["fast", t_fast, ".w", "settled"], ["late", t_late, ".w", "settled"]])
    assert not all(d["fast"]) and all(d["late"])
    P = _classic(5.0, title="Co Claude czyta", nodes=["Prompt", "Kontekst", "Pliki", "Odpowiedź"])
    d = _run_effect("flow", P, [["fast", t_fast, ".fl-node", "settled"], ["late", t_late, ".fl-node", "settled"]])
    assert not all(d["fast"]) and all(d["late"])
    P = _classic(5.0, value=75, suffix="%", label="tokenów zużytych mniej", note="źródło: README")
    d = _run_effect("stat-card", P, [["fast", 1.0 + 0.45 + 0.05, ".sc-label", "kids"], ["late", t_late, ".sc-note", "settled"]])
    assert not all(d["fast"][0]) and d["late"] == [True]                        # label words start at at + 0.45


def _node(js: str, *fmt) -> dict:
    r = subprocess.run(["node", "-e", js % fmt], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


SCRAMBLE = """
global.window = {};
require(%s);
const F = window.CutmateFX.pure;
const CH = "!<>-_\\\\/[]{}=+*^?#ABCDEFGHJKLMNPQRSTUVWXYZ0123456789";
const T = "GLOBALNIE";
console.log(JSON.stringify({
  a: F.scrambleAt(T, 0.3, 7, 1, CH), b: F.scrambleAt(T, 0.3, 7, 1, CH), seed2: F.scrambleAt(T, 0.3, 7, 2, CH),
  full: F.scrambleAt(T, 1, 99, 1, CH), over: F.scrambleAt(T, 1.7, 3, 1, CH), half: F.scrambleAt(T, 0.5, 10, 1, CH),
  f10: F.scrambleAt(T, 0.5, 10, 1, CH), f11: F.scrambleAt(T, 0.5, 11, 1, CH), zero: F.scrambleAt(T, 0, 4, 1, CH),
  neg: F.scrambleAt(T, -1, 4, 1, CH), sp: F.scrambleAt("ZA DARMO  OK", 0.1, 5, 3, CH),
  pl: F.scrambleAt("Zażółć", 0.5, 2, 1, CH), chars: CH,
}));
"""


def test_scramble_is_pure():
    """GSAP's ScrambleTextPlugin draws from Math.random; scrambleAt is a pure function of (text, p, frame, seed)."""
    d = _node(SCRAMBLE, json.dumps(str(web_dir() / "effects.js")))
    assert d["a"] == d["b"] and d["a"] != d["seed2"]                     # same args -> same string; the seed matters
    assert d["full"] == "GLOBALNIE" and d["over"] == "GLOBALNIE"          # p >= 1: the text
    assert d["half"][:5] == "GLOBA" and len(d["half"]) == 9               # round(0.5 * 9) = 5 characters final
    assert d["f10"][5:] != d["f11"][5:] and d["f10"][:5] == d["f11"][:5]  # the unrevealed tail changes per frame
    assert all(c in d["chars"] for c in d["half"][5:])
    assert len(d["zero"]) == 9 and d["zero"] != "GLOBALNIE" and d["neg"] == d["zero"]
    assert [i for i, c in enumerate(d["sp"]) if c == " "] == [2, 8, 9]   # spaces stay spaces
    assert len(d["sp"]) == 12 and d["sp"][0] == "Z"                       # round(0.1 * 12) = 1 final
    assert d["pl"][:3] == "Zaż" and len(d["pl"]) == 6                     # by character, not UTF-16 unit


OPEN = """
global.window = {};
require(%s);
const F = window.CutmateFX.pure;
const S = [[0, 0], [1, 1], [2, 0]];
const all = [];
for (let t = -1; t <= 4; t += 0.01) all.push(F.openAmount(S, t));
console.log(JSON.stringify({
  a: F.openAmount(S, 0.9), b: F.openAmount(S, 1.15), c: F.openAmount(S, 1.5), d: F.openAmount(S, 2.3),
  e: F.openAmount(S, 2.1), slow: F.openAmount(S, 1.15, 0.6), empty: F.openAmount([], 3), none: F.openAmount(null, 3),
  blip: F.openAmount([[0, 0], [1, 1], [1.1, 0]], 1.2),
  min: Math.min(...all), max: Math.max(...all),
}));
"""


def test_open_amount():
    d = _node(OPEN, json.dumps(str(web_dir() / "effects.js")))
    assert d["a"] == 0 and d["b"] == pytest.approx(0.5) and d["c"] == 1 and d["d"] == 0
    assert d["e"] == pytest.approx(0.6)                                   # falls over 0.25 s
    assert d["slow"] == pytest.approx(0.25)                               # rise = 0.6 s
    assert d["empty"] == 0 and d["none"] == 0
    assert d["blip"] == 0                                                 # 1/3 open, then falls past 0: clamped
    assert d["min"] >= 0 and d["max"] <= 1


TOKEN = """
global.window = {};
require(%s);
const root = { style: {} };
const seen = [];
let props = {};
global.document = { documentElement: {} };
global.getComputedStyle = (el) => { seen.push(el === root); return { getPropertyValue: (k) => props[k] || "" }; };
const U = window.CutmateFX.make({ to() {} }, root, "c1", { dur: 1 });
const out = {};
props = { "--accent": "  #c2501f ", "--font-display": "'Press Start 2P', monospace" };
out.accent = U.token("--accent", "#7dd3fc");
out.bare = U.token("accent", "#7dd3fc");
out.font = U.token("--font-display", "Inter");
props = { "--accent": "   " };
out.empty = U.token("--accent", "#7dd3fc");
out.missing = U.token("--panel-bg", "#0b0b0f");
out.onRoot = seen.every(Boolean);
global.getComputedStyle = undefined;
out.noDom = U.token("--accent", "#7dd3fc");
console.log(JSON.stringify(out));
"""


def test_token_reads_theme_and_falls_back():
    """Review Focus 3: canvas / WebGL effects take the theme's tokens (orange accent, pixel font) or the fallback when an
    older theme lacks one (no --panel-bg) or there is no DOM."""
    d = _node(TOKEN, json.dumps(str(web_dir() / "effects.js")))
    assert d["accent"] == "#c2501f" and d["bare"] == "#c2501f" and d["font"] == "'Press Start 2P', monospace"
    assert d["empty"] == "#7dd3fc" and d["missing"] == "#0b0b0f" and d["noDom"] == "#7dd3fc"
    assert d["onRoot"] is True                                            # read on the effect's root (cascade)


GSAP_JS = plugin_root() / "assets" / "vendor" / "gsap@3.14.2" / "dist" / "gsap.min.js"
ANIME_JS = plugin_root() / "assets" / "vendor" / "animejs@4.5.0" / "dist" / "bundles" / "anime.umd.min.js"

CLOCK_ORDER = """
global.window = {};
const G = require(%s);
const gsap = G.gsap || G;
require(%s);
const tl = gsap.timeline({ paused: true });
const U = window.CutmateFX.make(tl, {}, "c1", { dur: 4 });
const state = { v: -1 }, seen = [];
U.clock((t) => { state.v = Math.round(t * 1000); });           // the writer (e.g. an anime seek)
U.clock(() => { seen.push(state.v); });                         // a reader (e.g. DOM writes from the animated objects)
const out = [];
for (const t of [1.0, 3.0, 2.0, 0.5, 3.5]) { seen.length = 0; tl.totalTime(t, false); out.push([Math.round(t * 1000), seen.slice()]); }
console.log(JSON.stringify(out));
"""


def test_clocks_run_in_order_when_seeking_backwards():
    """GSAP renders a timeline's children last-to-first on a backward seek: every U.clock callback hangs off one tween, so
    a reader registered after a writer always sees this frame's state (a render worker scrubbing back)."""
    r = _node(CLOCK_ORDER, json.dumps(str(GSAP_JS)), json.dumps(str(web_dir() / "effects.js")))
    assert r == [[1000, [1000]], [3000, [3000]], [2000, [2000]], [500, [500]], [3500, [3500]]]


ANIME = """
let raf = 0;          // frames requested by anime.js or effects.js (GSAP's own ticker asks for one; HyperFrames owns it)
global.requestAnimationFrame = () => { if (/anime\\.umd|effects\\.js/.test(new Error().stack)) raf++; return 1; };
global.cancelAnimationFrame = () => {};
global.NodeList = class {}; global.HTMLCollection = class {}; global.SVGElement = class {};
global.window = { requestAnimationFrame, cancelAnimationFrame };
global.document = { addEventListener() {}, removeEventListener() {}, hidden: false };
const A = require(%s);
const G = require(%s);
const gsap = G.gsap || G;
require(%s);
const make = () => {
  const objs = Array.from({ length: 50 }, () => ({ x: 0, y: 0, s: 1, r: 0 }));
  const at = A.createTimeline({ autoplay: false });
  at.add(objs, { x: [0, 100], y: [0, -50], s: [1, 0.2], ease: "outExpo", duration: 900,
                 delay: A.stagger(30, { grid: [10, 5], from: "center" }) }, 0)
    .add(objs, { r: 360, x: 300, ease: "outExpo", duration: 600, delay: A.stagger(12, { grid: [10, 5], from: "first" }) }, 1400)
    .add(objs, { y: 400, ease: "inBack", duration: 500, delay: A.stagger(8) }, 2600);
  return { objs, at };
};
// one effect = one paused GSAP timeline; U.anime seeks the anime timeline from it, a second clock copies the objects
// out (as an effect writes them to the DOM / canvas)
const effect = (cid, setup) => {
  const tl = gsap.timeline({ paused: true });
  const U = window.CutmateFX.make(tl, {}, cid, { dur: 4 });
  const m = make(), shown = [];
  const back = U.anime(setup ? setup(m.at) : m.at);
  U.clock(() => { shown.length = 0; m.objs.forEach((o) => shown.push(Object.assign({}, o))); });
  return { tl, shown, back, at: m.at };
};
const flat = (xs) => xs.map((o) => [o.x, o.y, o.s, o.r]);
const maxd = (a, b) => { let d = 0; flat(a).forEach((o, i) => o.forEach((v, k) => { d = Math.max(d, Math.abs(v - flat(b)[i][k])); })); return d; };
const res = { raf: 0 };
const one = effect("c1");
const seek = (e, t) => e.tl.totalTime(t, false);   // as the HyperFrames runtime seeks
seek(one, 2.0);
const direct = JSON.parse(JSON.stringify(one.shown));
res.same = one.back === one.at;
res.moved = direct[0].x > 0 && direct[0].x !== direct[49].x;
const two = effect("c2");
for (const t of [0.5, 3.0, 2.0]) seek(two, t);                   // forward, then a scrub back
res.scrub = maxd(direct, two.shown);
const three = effect("c3");
for (const t of [3.9, 0.2, 2.0]) seek(three, t);
res.scrub2 = maxd(direct, three.shown);
res.hfAnime = (window.__hfAnime || []).length;
// async setup (fonts first): a real timeline handed over as { timeline } (awaiting a paused timeline never ends)
const four = effect("c4", (at) => Promise.resolve().then(() => ({ timeline: at })));
window.__hf.buildReady.c4.then(() => {
  seek(four, 3.0); seek(four, 2.0);
  res.async = maxd(direct, four.shown);
  res.raf = raf;
  console.log(JSON.stringify(res));
});
"""


def test_anime_seek_order_independent():
    """anime.js 4.5 (autoplay: false) seeked by U.anime from a real paused GSAP timeline: a frame reached directly equals
    the same frame reached after other seeks, forwards and backwards (a render worker starting mid-effect), and nothing
    schedules a requestAnimationFrame."""
    d = _node(ANIME, json.dumps(str(ANIME_JS)), json.dumps(str(GSAP_JS)), json.dumps(str(web_dir() / "effects.js")))
    assert d["moved"] and d["same"]
    assert d["scrub"] <= 1e-9 and d["scrub2"] <= 1e-9 and d["async"] <= 1e-9
    assert d["raf"] == 0 and d["hfAnime"] == 0                    # never on window.__hfAnime (global-time seeking)


ANIME_P = """
global.window = {};
require(%s);
const updates = [];
const tl = { to(target, vars) { if (vars && vars.onUpdate) updates.push([target, vars]); return tl; } };
const seek = (t) => updates.forEach(([c, v]) => { c.t = t; v.onUpdate(); });
const seeks = [], seeks2 = [];
const at = { seek(ms) { seeks.push(ms); } };
// a real anime timeline is thenable (then() waits for it to finish): wrapped as { timeline } it is never awaited
const at2 = { seek(ms) { seeks2.push(ms); }, then() { throw new Error("awaited an anime timeline"); } };
const U = window.CutmateFX.make(tl, {}, "c1", { dur: 3 });
const p = Promise.resolve(at);
const back = U.anime(p);
const registered = !!(window.__hf && window.__hf.buildReady && window.__hf.buildReady.c1);
const U2 = window.CutmateFX.make(tl, {}, "c2", { dur: 3 });
U2.anime(Promise.resolve().then(() => ({ timeline: at2 })));
seek(1.5);
const before = seeks.length + seeks2.length;
Promise.all([window.__hf.buildReady.c1, window.__hf.buildReady.c2]).then(() => {
  const afterReady = seeks.slice(), afterReady2 = seeks2.slice();
  seek(2.0);
  console.log(JSON.stringify({ registered, before, afterReady, afterReady2, last: seeks[seeks.length - 1],
                               last2: seeks2[seeks2.length - 1], clocks: updates.length, same: back === p }));
});
"""


def test_anime_promise_waits_ready():
    d = _node(ANIME_P, json.dumps(str(web_dir() / "effects.js")))
    assert d["registered"] and d["same"] and d["clocks"] == 2
    assert d["before"] == 0                                         # the clock is a no-op before the timeline exists
    assert d["afterReady"] == [1500]                                # once it exists: seeked to the clock's current time
    assert d["last"] == 2000
    assert d["afterReady2"] == [1500] and d["last2"] == 2000        # { timeline } form: never awaited


ANIME_BAD = """
global.requestAnimationFrame = () => 1; global.cancelAnimationFrame = () => {};
global.NodeList = class {}; global.HTMLCollection = class {}; global.SVGElement = class {};
global.window = { requestAnimationFrame, cancelAnimationFrame };
global.document = { addEventListener() {}, removeEventListener() {}, hidden: false };
window.anime = require(%s);
require(%s);
const A = window.anime;
const tl = { to() { return tl; } };
const res = {};
const err = (e) => String(e && e.message || e);
try { window.CutmateFX.make(tl, {}, "c0", { dur: 2 }).anime(42); } catch (e) { res.sync = err(e); }
const at = A.createTimeline({ autoplay: false });
window.CutmateFX.make(tl, {}, "c1", { dur: 2 }).anime(Promise.resolve().then(() => at));      // a bare timeline
window.CutmateFX.make(tl, {}, "c2", { dur: 2 }).anime(Promise.resolve({ nope: 1 }));
window.CutmateFX.make(tl, {}, "c3", { dur: 2 }).anime(Promise.resolve().then(() => ({ timeline: at })));
Promise.allSettled(["c1", "c2", "c3"].map((c) => window.__hf.buildReady[c])).then((r) => {
  res.bare = r[0].status === "rejected" ? err(r[0].reason) : "resolved";
  res.junk = r[1].status === "rejected" ? err(r[1].reason) : "resolved";
  res.ok = r[2].status;
  console.log(JSON.stringify(res));
});
"""


def test_anime_promise_wrong_value_is_a_one_line_error():
    """A promise resolving to a bare anime timeline (thenable: it would wait forever for a paused timeline to finish) or to
    junk rejects buildReady with a one-line error instead of hanging the render."""
    d = _node(ANIME_BAD, json.dumps(str(ANIME_JS)), json.dumps(str(web_dir() / "effects.js")))
    assert d["ok"] == "fulfilled"
    assert "{ timeline: tl }" in d["bare"] and "\n" not in d["bare"]
    assert "{ timeline: tl }" in d["junk"] and "object" in d["junk"]
    assert "{ timeline: tl }" in d["sync"]


# WOW explainers (exploded-view, globe): their pure helpers, registered on window.CutmateFX.wow by the effect file.
# The effect script runs as in a composition, with U.three stubbed out (no WebGL in node): only the helpers matter here
WOW = """
global.window = {};
require(%s);
const tl = { to() { return tl; }, set() { return tl; }, fromTo() { return tl; } };
// any DOM access before the (never resolving) U.three promise gets an inert stand-in
const stub = () => new Proxy(function () {}, { get: (o, k) => (k === Symbol.toPrimitive ? () => "" : stub()), apply: () => stub(),
                                               set: () => true });
const root = stub();
for (const src of %s) {
  const U = window.CutmateFX.make(tl, {}, "c1", { dur: 4 });
  U.three = () => new Promise(() => {});
  new Function("tl", "root", "P", "U", src)(tl, root, { at: 0.5, end: 3.5, dur: 4, w: 1000, h: 880, lang: "pl" }, U);
}
const W = window.CutmateFX.wow;
console.log(JSON.stringify((function () { %s })()));
"""


def _wow(body: str, names=("exploded-view", "globe")) -> dict:
    from cutmate.build import _sections
    fx = plugin_root() / "themes" / "clean" / "components" / "custom"
    srcs = [_sections(fx / f"{n}.html")["script"] for n in names]
    return _node(WOW, json.dumps(str(web_dir() / "effects.js")), json.dumps(srcs), body)


def test_explode_layout():
    d = _wow("""
      const out = {};
      for (const n of [2, 3, 5, 7]) out[n] = { k0: W.explodeLayout(n, "y", 0), k1: W.explodeLayout(n, "y", 1),
                                              half: W.explodeLayout(n, "y", 0.5), x1: W.explodeLayout(n, "x", 1) };
      out.slab = W.SLAB;
      out.heights = W.explodeLayout([0.3, 0.8, 0.12], "y", 0);
      out.heights1 = W.explodeLayout([0.3, 0.8, 0.12], "y", 1);
      return out;""", names=("exploded-view",))
    slab = d["slab"]
    assert slab > 0
    for n in ("2", "3", "5", "7"):
        k0, k1, x1, half = d[n]["k0"], d[n]["k1"], d[n]["x1"], d[n]["half"]
        assert len(k0) == len(k1) == len(x1) == int(n) and all(len(p) == 3 for p in k0 + k1)
        gaps0 = [b[1] - a[1] - slab for a, b in zip(k0, k0[1:])]
        gaps1 = [b[1] - a[1] - slab for a, b in zip(k1, k1[1:])]
        assert all(abs(g) <= 0.01 for g in gaps0), (n, gaps0)              # assembled: every part touches the next
        assert all(g >= 0.15 for g in gaps1), (n, gaps1)                   # exploded: never overlapping
        assert all(0.0 < (b[1] - a[1] - slab) < g1 for a, b, g1 in zip(half, half[1:], gaps1))   # k between
        for L in (k0, k1):                                                  # symmetric about the centre
            for i in range(len(L)):
                assert all(abs(L[i][j] + L[-1 - i][j]) <= 1e-9 for j in range(3)), (n, L)
        assert all(abs(k0[i][0]) <= 1e-9 for i in range(len(k0)))         # no fan while assembled
        for p, q in zip(k1, x1):                                            # axis "x": the axes swap
            assert abs(q[0] - p[1]) <= 1e-9 and abs(q[1] - p[0]) <= 1e-9 and abs(q[2] - p[2]) <= 1e-9
    hs, h0, h1 = [0.3, 0.8, 0.12], d["heights"], d["heights1"]
    assert all(abs((b[1] - a[1]) - (ha + hb) / 2) <= 1e-9 for a, b, ha, hb in zip(h0, h0[1:], hs, hs[1:]))
    assert all((b[1] - a[1]) - (ha + hb) / 2 >= 0.15 for a, b, ha, hb in zip(h1, h1[1:], hs, hs[1:]))


def _countries():
    p = plugin_root() / "themes" / "clean" / "components" / "custom" / "globe" / "countries.json"
    return json.loads(p.read_text(encoding="utf-8"))


def test_globe_math():
    c = _countries()
    pl, us = c["PL"], c["US"]
    d = _wow(f"""
      const a = W.arcPoints({pl['lat']}, {pl['lng']}, {us['lat']}, {us['lng']});
      const b = W.arcPoints({pl['lat']}, {pl['lng']}, {us['lat']}, {us['lng']}, 17);
      return {{ zero: W.latLngToVec(0, 0, 1), north: W.latLngToVec(90, 0, 1), east: W.latLngToVec(0, 90, 2),
               pl: W.latLngToVec({pl['lat']}, {pl['lng']}, 1), us: W.latLngToVec({us['lat']}, {us['lng']}, 1), a, b }};""",
             names=("globe",))
    import math
    close = lambda u, v, e=1e-9: all(abs(x - y) <= e for x, y in zip(u, v))  # noqa: E731
    assert close(d["zero"], [0, 0, 1]) and close(d["north"], [0, 1, 0]) and close(d["east"], [2, 0, 0])
    a = d["a"]
    norm = lambda v: math.sqrt(sum(x * x for x in v))  # noqa: E731
    assert len(a) == 64 and len(d["b"]) == 17
    assert abs(norm(a[0]) - 1) <= 1e-6 and abs(norm(a[-1]) - 1) <= 1e-6        # starts / ends on the sphere
    assert close(a[0], d["pl"], 1e-6) and close(a[-1], d["us"], 1e-6)
    hs = [norm(p) - 1 for p in a]
    top = max(range(len(hs)), key=hs.__getitem__)
    assert top in (31, 32)                                                       # the apex is in the middle
    ang = math.acos(sum(x * y for x, y in zip(d["pl"], d["us"])))
    apex = 0.15 + 0.35 * ang / math.pi
    assert apex * 0.99 <= hs[top] <= apex + 1e-9
    assert all(h >= -1e-9 for h in hs)                                            # never under the surface


def test_globe_frames_every_point():
    """At 0.8 of the span the pose (pure, shared with the hf test) shows the origin and every destination in front,
    inside the region with room to spare."""
    c = _countries()
    ll = lambda k: [c[k]["lat"], c[k]["lng"]]  # noqa: E731
    for w, h, panel, title in ((1000, 880, True, ""), (1080, 1920, False, "Zasięg"), (840, 960, False, "")):
        o = {"from": ll("PL"), "to": [ll("US"), ll("JP"), ll("BR")], "w": w, "h": h, "at": 0.5, "end": 3.5,
             "panel": panel, "title": title}
        d = _wow(f"""
          const o = {json.dumps(o)};
          const pose = W.globePose(o, 0.5 + 0.8 * 3.0);
          return [o.from, ...o.to].map((p) => W.globeProject(pose, W.latLngToVec(p[0], p[1], 1), o.w, o.h));""",
                 names=("globe",))
        for x, y, front in d:
            assert front > 0.05, (w, h, d)
            assert 0.06 * w <= x <= 0.94 * w and 0.06 * h <= y <= 0.94 * h, (w, h, d)


SAFE = """
global.window = {};
require(%s);
const F = window.CutmateFX.pure;
console.log(JSON.stringify({ none: F.safeBox({ w: 1080, h: 1920 }), bottom: F.safeBox({ w: 1080, h: 1920, caption_band: [1295, 1455] }),
  top: F.safeBox({ w: 1000, h: 880, caption_band: [0, 300] }), edge: F.safeBox({ w: 1000, h: 880, caption_band: [840, 880] }) }));
"""


def test_safe_box_avoids_the_caption_band():
    d = _node(SAFE, json.dumps(str(web_dir() / "effects.js")))
    assert d["none"] == {"x": 0, "y": 0, "w": 1080, "h": 1920}
    b = d["bottom"]
    assert b["y"] == 0 and b["w"] == 1080 and 1250 < b["h"] < 1295            # above the band, a pad off it
    t = d["top"]
    assert t["y"] > 300 and abs(t["y"] + t["h"] - 880) < 1e-6                  # the bigger side: below
    e = d["edge"]
    assert e["y"] == 0 and 820 < e["h"] < 840


HITS = """
global.window = {};
global.document = { getElementById: () => ({ appendChild: (c) => c }), createElement: () => ({ appendChild: (c) => c }) };
const calls = [];
const tl = {};
for (const m of ["set", "to", "fromTo"]) tl[m] = (t, a, b, c) => { calls.push([m, t, m === "fromTo" ? b : a, a]); return tl; };
require(%s);
const out = {};
for (const [k, cfg] of Object.entries(%s)) {
  calls.length = 0;
  window.Cutmate.build(tl, cfg);
  out[k] = calls.filter(([m, t, v]) => m === "to" && v && v.keyframes).map(([, t]) => t)
    .concat(calls.filter(([m, t, v]) => m === "set" && v && "rotation" in v).map(([, t]) => t));
  out[k + "_flash"] = calls.filter(([m, t, v, f]) => m === "fromTo" && t === "#flash").map((c) => c[3].opacity);
}
console.log(JSON.stringify(out));
"""


def test_hits_shake_hosts():
    """cfg.shake_hosts (a bg effect drawing the speaker cut-out): every hit shakes "#shake, .cm-shake"; otherwise "#shake"."""
    base = {"end": 4.0, "pages": [], "cam": [[0, 1.0]], "hits": [[1.0, 1.0, 0]], "splits": []}
    d = _node(HITS, json.dumps(str(web_dir() / "cutmate.js")),
              json.dumps({"hosts": {**base, "shake_hosts": True}, "plain": base}))
    assert d["hosts"] == ["#shake, .cm-shake", "#shake, .cm-shake"]
    assert d["plain"] == ["#shake", "#shake"]
    assert d["hosts_flash"] == [0.8] and d["plain_flash"] == [0.8]
    soft = {**base, "hits": [[1.0, 1.0, 0, 0.35], [2.0, 1.0, 0]], "shake_hosts": True}
    assert _node(HITS, json.dumps(str(web_dir() / "cutmate.js")), json.dumps({"s": soft}))["s_flash"] == [0.35, 0.8]


# burst-out: the effect script as in a bg composition (root > .bo-gl canvas layer, the cut-out .clip video in its own
# layer), U.three stubbed (no WebGL in node); every tl.set recorded, so the layer order is read at any time
BURST = """
global.window = {};
require(%(fx)s);
class El {
  constructor(tag, cls) { this.tagName = tag; this.cls = new Set((cls || "").split(" ").filter(Boolean)); this.children = [];
    this.parentNode = null; this.style = { setProperty() {} }; this.attrs = {}; this._text = "";
    const self = this; this.classList = { add: (c) => self.cls.add(c), contains: (c) => self.cls.has(c), remove: (c) => self.cls.delete(c) }; }
  appendChild(c) { c.parentNode = this; this.children.push(c); return c; }
  remove() {} setAttribute(k, v) { this.attrs[k] = v; }
  get textContent() { return this._text; } set textContent(v) { this._text = String(v); }
  all() { return this.children.reduce((a, c) => a.concat([c], c.all()), []); }
  querySelectorAll(sel) { const c = sel.replace(/^[a-z]*\\./, ""); return this.all().filter((e) => e.cls.has(c)); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
}
global.document = { createElement: (t) => new El(t), documentElement: new El("html") };
global.getComputedStyle = () => ({ getPropertyValue: () => "", color: "" });
const sets = [];
const tl = { to() { return tl; }, fromTo() { return tl; }, set(t, v, pos) { sets.push([t, v, pos]); return tl; } };
const root = new El("div");
const bo = root.appendChild(new El("div", "bo"));
const gl = bo.appendChild(new El("div", "bo-gl"));
const cut = bo.appendChild(new El("div", "bo-cut"));
const video = cut.appendChild(new El("video", "clip"));
bo.appendChild(new El("div", "bo-label")).appendChild(new El("span", "bo-k"));
const P = %(params)s;
const U = Object.assign(window.CutmateFX.make(tl, root, "c1", P), { el(tag, cls, text, parent) { const e = new El(tag, cls);
  if (text != null) e.textContent = text; (parent || root).appendChild(e); return e; } });
U.three = () => new Promise(() => {});
U.post = () => new Promise(() => {});
%(script)s
const z = (el, T) => { let v; sets.filter(([t, s, pos]) => t === el && "zIndex" in s && pos <= T + 1e-9)
  .sort((a, b) => a[2] - b[2]).forEach(([, s]) => { v = s.zIndex; }); return v; };
const layer = (el, T) => { for (let e = el; e; e = e.parentNode) { const v = z(e, T); if (v !== undefined) return v; } };
const W = window.CutmateFX.wow;
const o = W.burstSpec(P);
console.log(JSON.stringify({ gl: %(times)s.map((T) => layer(gl, T)), cut: %(times)s.map((T) => layer(video, T)),
  path: %(path_times)s.map((T) => W.burstPath(o, T)), spec: o }));
"""


def _burst(params: dict, times: list, path_times: list) -> dict:
    from cutmate.build import _sections
    sec = _sections(plugin_root() / "themes" / "clean" / "components" / "custom" / "burst-out.html")
    assert "{{cut_tag}}" in sec["markup"] and sec["markup"].index('class="bo-gl"') < sec["markup"].index("{{cut_tag}}")
    js = BURST % {"fx": json.dumps(str(web_dir() / "effects.js")), "params": json.dumps(params), "script": sec["script"],
                  "times": json.dumps(times), "path_times": json.dumps(path_times)}
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_burst_out_layers():
    """The canvas is under the cut-out until P.hit_at and above it from then on; the object lands on the side away from
    the face and never covers it (nor the caption band) from 1.2 s on."""
    P = {"at": 0.2, "end": 3.6, "hit_at": 1.0, "dur": 3.6, "w": 1080, "h": 1920, "lang": "pl", "face": [380, 700],
         "caption_band": [1295, 1455], "label": "Gotowe"}
    ts = [round(1.2 + 0.1 * i, 2) for i in range(int((3.6 - 1.2) / 0.1))]
    d = _burst(P, [0.3, 0.9, 1.05, 2.0], ts)
    gl, cut = d["gl"], d["cut"]
    assert gl[0] < cut[0] and gl[1] < cut[1]                                 # behind the speaker before the hit
    assert gl[2] > cut[2] and gl[3] > cut[3]                                 # in front of him after it
    hr = d["spec"]["head"]
    for p in d["path"]:
        assert p["x"] > 540, p                                               # face x < W/2 -> the right side
        if p["s"] > 0.05:
            r = p["r"]
            assert ((p["x"] - 380) ** 2 + (p["y"] - 700) ** 2) ** 0.5 >= r + hr, p    # clear of the face
            assert p["y"] + r <= 1295, p                                     # clear of the burned captions
    P2 = dict(P, face=[760, 700])                                            # face on the right -> the left side
    d = _burst(P2, [0.3], ts)
    assert all(p["x"] < 540 for p in d["path"])
    d = _burst({k: v for k, v in P.items() if k != "hit_at"}, [0.3, 1.15, 1.25], [])   # default hit: at + 1.0
    assert d["gl"][1] < d["cut"][1] and d["gl"][2] > d["cut"][2]


def test_burst_out_overshoots_at_the_hit():
    """The "flies at the camera" beat: the object is ~1.25x its held size on the impact word, then settles to 1.0 (no
    second pop); the label under the held object keeps a clear gap above the burned captions."""
    P = {"at": 0.2, "end": 3.6, "hit_at": 1.0, "dur": 3.6, "w": 1080, "h": 1920, "lang": "pl", "face": [380, 700],
         "caption_band": [1295, 1455], "label": "Gotowe"}
    after = [round(1.05 + 0.05 * i, 2) for i in range(int((3.6 - 0.35 - 1.05) / 0.05))]
    d = _burst(P, [0.3], [0.99, 1.0, 1.02, *after, 2.7])
    s = [p["s"] for p in d["path"]]
    assert 1.18 <= s[1] <= 1.32, s[:3]
    assert max(s[3:]) <= s[1] + 1e-9 and max(s[3:]) <= 1.3
    assert 0.96 <= s[-1] <= 1.04, s[-1]
    o = d["spec"]
    label_bottom = o["cy"] + o["R"] + 0.02 * 1080 + o["labelPx"] * 1.9
    assert 1295 - label_bottom >= 60, label_bottom


# hand-control: the effect script with a tiny DOM (style objects kept), a no-op 2D canvas, U.fonts / U.ready resolved;
# the clock is seeked to each probe time and the card's transform / the pure tipSparks are read
HAND = """
global.window = {};
require(%(fx)s);
const noop = new Proxy(function () {}, { get: (f, k) => (k === "canvas" ? undefined : noop), apply: () => noop });
class El {
  constructor(tag) { this.tagName = String(tag).toUpperCase(); this.children = []; this.parentNode = null; this._cls = new Set();
    this.style = { setProperty(k, v) { this[k] = v; } }; this.attrs = {}; this._text = ""; this.offsetWidth = 0; this.offsetHeight = 0;
    this.dataset = {}; const self = this;
    this.classList = { add: (...c) => c.forEach((x) => self._cls.add(x)), remove: (...c) => c.forEach((x) => self._cls.delete(x)),
      contains: (c) => self._cls.has(c), toggle: (c, on) => (on ? self._cls.add(c) : self._cls.delete(c)) }; }
  get className() { return Array.from(this._cls).join(" "); }
  set className(v) { this._cls = new Set(String(v).split(/\\s+/).filter(Boolean)); }
  get textContent() { return this._text; } set textContent(v) { this._text = String(v); }
  appendChild(c) { c.parentNode = this; this.children.push(c); return c; }
  remove() {} setAttribute(k, v) { this.attrs[k] = String(v); }
  getContext() { return noop; }
  all() { return this.children.reduce((a, c) => a.concat([c], c.all()), []); }
  querySelectorAll(sel) { const c = sel.replace(/^[a-z]*\\./, ""); return this.all().filter((e) => e._cls.has(c)); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
}
global.document = { createElement: (t) => new El(t), createElementNS: (n, t) => new El(t), documentElement: new El("html") };
global.getComputedStyle = () => ({ getPropertyValue: () => "", color: "" });
const updates = [];
const tl = { to(target, vars) { if (vars && vars.onUpdate) updates.push([target, vars]); return tl; }, set() { return tl; },
             fromTo() { return tl; } };
const root = new El("div");
const mk = %(markup)s.match(/class="([^"]+)"/);
if (mk) root.appendChild(new El("div")).className = mk[1];
const P = %(params)s;
const U = Object.assign(window.CutmateFX.make(tl, root, "c1", P), {
  el(tag, cls, text, parent) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; (parent || root).appendChild(e); return e; },
});
U.fonts = () => Promise.resolve();
%(script)s
const seek = (t) => updates.forEach(([c, v]) => { c.t = t; v.onUpdate(); });
const W = window.CutmateFX.wow;
const out = { scaleY: [], sparks: [], hidden: [] };
for (const t of %(times)s) {
  seek(t);
  const card = root.querySelector(".hc-card");
  const mm = String(card.style.transform || "").match(/scaleY\\(([-\\d.e]+)\\)/);
  out.scaleY.push(mm ? Number(mm[1]) : null);
  out.hidden.push(String(card.style.visibility));
  out.sparks.push(W.tipSparks(P, t));
}
console.log(JSON.stringify(out));
"""


def _hand_control(params: dict, times: list) -> dict:
    from cutmate.build import _sections
    sec = _sections(plugin_root() / "themes" / "clean" / "components" / "custom" / "hand-control.html")
    js = HAND % {"fx": json.dumps(str(web_dir() / "effects.js")), "markup": json.dumps(sec.get("markup", "")),
                 "params": json.dumps(params), "script": sec["script"], "times": json.dumps(times)}
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def _hc_params(open_from=None, open_to=None, ext=(1, 1, 1, 1, 1), **kw):
    """A 1080x1920 overlay 0.2–3.8 s: the right palm at (540, 1100), five tips fanned 160 px above it (step 0.1 s)."""
    ts = [round(0.1 * i, 2) for i in range(40)]
    tips = [[[t, 380 + 80 * k, 940 - (40 if k in (1, 2, 3) else 0), float(ext[k])] for t in ts] for k in range(5)]
    po = [[t, 1 if open_from is not None and open_from <= t < open_to else 0] for t in ts]
    P = {"at": 0.2, "end": 3.8, "dur": 3.8, "w": 1080, "h": 1920, "lang": "pl", "lift": 96.0,
         "card": {"title": "Karta", "lines": ["jeden", "dwa"]}, "tips": {"right": tips}, "palm_open": {"right": po},
         "palms": {"right": [[t, 540, 1100] for t in ts]}}
    P.update(kw)
    return P


def test_card_stays_folded_without_open_palm():
    """Review Focus 4: no open palm -> the card stays folded (scaleY <= 0.01) all the time; an open palm from 1.0 s
    unfolds it (folded at 1.0, fully open and settled at 1.35) and it folds back within 0.25 s of the palm closing; no
    palm track at all -> hidden."""
    probes = [round(0.1 * i, 2) for i in range(39)]
    d = _hand_control(_hc_params(), probes)
    assert all(s is not None and s <= 0.01 for s in d["scaleY"]), d["scaleY"]
    d = _hand_control(_hc_params(1.0, 2.0), [1.0, 1.35, 1.6, 1.99, 2.25, 2.6])
    assert d["scaleY"][0] <= 0.01
    assert abs(d["scaleY"][1] - 1) <= 0.001 and abs(d["scaleY"][2] - 1) <= 0.001 and abs(d["scaleY"][3] - 1) <= 0.001
    assert d["scaleY"][4] <= 0.01 and d["scaleY"][5] <= 0.01
    d = _hand_control(_hc_params(1.0, 3.0, palms={}, tips={}, palm_open={}), [1.5, 2.0])
    assert all(v == "hidden" for v in d["hidden"])


def test_sparks_only_from_extended_tips():
    """The pure tipSparks(P, t) on window.CutmateFX.wow: particles come only from tips flagged extended (index, middle
    here), stay near them, at most 120 per tip; none with sparks "off", none before P.at, none once a finger is gone."""
    P = _hc_params(ext=(0, 1, 1, 0, 0))
    d = _hand_control(P, [0.1, 1.0, 2.0])
    assert d["sparks"][0] == []
    for sp in d["sparks"][1:]:
        assert sp and {p["tip"] for p in sp} == {1, 2}
        assert len(sp) <= 2 * 120
        for p in sp:
            ex, ey = P["tips"]["right"][p["tip"]][0][1:3]
            assert (p["ex"], p["ey"]) == (ex, ey)
            assert ((p["x"] - ex) ** 2 + (p["y"] - ey) ** 2) ** 0.5 < 0.3 * 1920
    assert _hand_control(dict(P, sparks="off"), [1.0, 2.0])["sparks"] == [[], []]
    gone = _hc_params(ext=(0, 1, 1, 0, 0))
    gone["tips"]["right"] = [[s for s in tip if s[0] <= 1.0] for tip in gone["tips"]["right"]]
    assert _hand_control(gone, [2.0])["sparks"] == [[]]                 # last seen at 1.0 s: no sparks a second later


def test_card_keeps_off_the_face():
    """A palm just under the face (hands up at the chest): the open card slides sideways off the tracked face (toward the
    hand's side) instead of covering it; it stays inside the SAFE box. Without a face track it sits on the hinge, which is
    above the highest fingertip (the fingers and their sparks stay visible under the card)."""
    js = HAND.split("const seek = ")[0] + """
const W = window.CutmateFX.wow, out = {};
const near = Array.from({ length: 40 }, (_, i) => [i / 10, 900, 260]);
for (const [k, faces] of [["face", near], ["none", []]]) {
  const p = Object.assign({}, P, { faces }), o = W.cardPose(p, 2.0, 300);
  out[k] = { cx: o.cx, by: o.by, w: o.cw * o.s, h: o.ch * o.s, open: o.open };
}
console.log(JSON.stringify(out));
"""
    from cutmate.build import _sections
    sec = _sections(plugin_root() / "themes" / "clean" / "components" / "custom" / "hand-control.html")
    ts = [round(0.1 * i, 2) for i in range(40)]
    P = {"at": 0.2, "end": 3.8, "dur": 3.8, "w": 1920, "h": 1080, "lang": "pl", "lift": 54.0, "safe": [60, 60, 1800, 800],
         "card": {"title": "Karta"}, "tips": {"right": [[[t, 960, 500, 1.0] for t in ts]] * 5},
         "palm_open": {"right": [[t, 1] for t in ts]}, "palms": {"right": [[t, 960, 600] for t in ts]}}
    r = subprocess.run(["node", "-e", js % {"fx": json.dumps(str(web_dir() / "effects.js")), "markup": json.dumps(sec["markup"]),
                                            "params": json.dumps(P), "script": sec["script"], "times": "[]"}],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[-3000:]
    d = json.loads(r.stdout.strip().splitlines()[-1])
    none, face = d["none"], d["face"]
    # bottom-centre on the hinge: above the highest fingertip (y 500 - 0.035·1080), not P.lift above the palm (546)
    assert none["open"] == 1 and none["cx"] == 960 and none["by"] == pytest.approx(500 - 0.035 * 1080)
    assert none["w"] == 760                                                        # 16:9: clamp(0.5·W, 420, 760)
    assert face["w"] >= 0.6 * 760                                                  # smaller beside the face, not over it
    fr, fy = 0.17 * 1080, 260 - 0.02 * 1080
    x0, x1, y0, y1 = face["cx"] - face["w"] / 2, face["cx"] + face["w"] / 2, face["by"] - face["h"], face["by"]
    nx, ny = min(max(900, x0), x1), min(max(fy, y0), y1)
    assert ((nx - 900) ** 2 + (ny - fy) ** 2) ** 0.5 >= fr - 1e-6, face           # clear of the face
    assert face["cx"] > 900 and x0 >= 60 and x1 <= 1860 and y0 >= 60               # the hand's side, inside SAFE


def test_flick_burst_and_edge_sparks():
    """A finger flicking out (ext 0 -> 1 at 1.0 s) fires a radial burst from that tip only, gone after 0.45 s; the sparks
    are bold (core 4–8 px, glow 12–20 px at 1080) with 90–140 ms tails; an open card spills sparks from its bottom edge
    (layer above the card), none while it is folded."""
    P = _hc_params(1.0, 3.0, ext=(0, 0, 0, 0, 0))
    P["tips"]["right"][1] = [[s[0], s[1], s[2], 1.0 if s[0] >= 1.0 else 0.0] for s in P["tips"]["right"][1]]
    js = HAND.split("const seek = ")[0] + """
const W = window.CutmateFX.wow, out = {};
for (const t of [0.9, 1.1, 1.6]) out[t] = { tips: W.tipSparks(P, t), edge: W.edgeSparks(P, t, W.cardPose(P, t, 400)) };
console.log(JSON.stringify(out));
"""
    from cutmate.build import _sections
    sec = _sections(plugin_root() / "themes" / "clean" / "components" / "custom" / "hand-control.html")
    r = subprocess.run(["node", "-e", js % {"fx": json.dumps(str(web_dir() / "effects.js")), "markup": json.dumps(sec["markup"]),
                                            "params": json.dumps(P), "script": sec["script"], "times": "[]"}],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[-3000:]
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d["0.9"]["tips"] == [] and d["0.9"]["edge"] == []
    burst = [p for p in d["1.1"]["tips"] if p["burst"]]
    assert len(burst) == 24 and {p["tip"] for p in d["1.1"]["tips"]} == {1}
    assert not any(p["burst"] for p in d["1.6"]["tips"]) and d["1.6"]["tips"]
    for p in d["1.6"]["tips"]:
        assert 4 <= p["size"] <= 8 and 12 <= p["glow"] <= 20
        if 0.09 <= p["age"] <= 0.15:                                             # young streaks: 60+ px long
            assert ((p["x"] - p["tx"]) ** 2 + (p["y"] - p["ty"]) ** 2) ** 0.5 > 60, p
    assert d["1.6"]["edge"] and d["1.1"]["edge"]


# the A-roll glitch on the main timeline (cutmate.js glitch(), cfg.glitch): every tl call recorded as
# [method, target, vars (the "to" vars of a fromTo), position]
GLITCH = """
global.window = {};
global.document = { getElementById: () => ({ appendChild: (c) => c }), createElement: () => ({ appendChild: (c) => c }) };
const calls = [];
const tl = {};
for (const m of ["set", "to", "fromTo"]) tl[m] = (t, a, b, c) => { calls.push([m, t, m === "fromTo" ? b : a, m === "fromTo" ? c : b]); return tl; };
require(%s);
const out = {};
for (const [k, cfg] of Object.entries(%s)) {
  calls.length = 0;
  window.Cutmate.build(tl, cfg);
  out[k] = JSON.parse(JSON.stringify(calls));
}
console.log(JSON.stringify(out));
"""


def _glitch_calls(cfgs: dict) -> dict:
    return _node(GLITCH, json.dumps(str(web_dir() / "cutmate.js")), json.dumps(cfgs))


def test_glitch_runtime():
    """cfg.glitch [[t, dur, kind]]: #split gets the SVG filter at t and loses it at t + dur; the R / B feOffset dx steps
    from ±18 px down to exactly 0 by t + dur (kind glitch), the displacement scale 60 -> 0 (kind wave); #shake jitters in
    deterministic steps. No cfg.glitch -> none of it."""
    base = {"end": 6.0, "pages": [], "cam": [[0, 1.0]], "hits": [], "splits": []}
    d = _glitch_calls({"g": {**base, "glitch": [[4, 0.6, "glitch"]]}, "g2": {**base, "glitch": [[4, 0.6, "glitch"]]},
                       "w": {**base, "glitch": [[4, 0.6, "wave"]]}, "none": base})
    g = d["g"]
    filt = [(c[3], c[2]["filter"]) for c in g if c[1] == "#split" and "filter" in (c[2] or {})]
    assert (4, "url(#cm-rgb)") in filt and (4.6, "none") in filt and (0, "none") in filt
    assert all(f in ("none", "url(#cm-rgb)") for _, f in filt)

    def end(c):
        v = c[2] or {}
        return c[3] + (sum(k.get("duration", 0) for k in v["keyframes"]) if "keyframes" in v else v.get("duration", 0))

    def last_attr(c, key):
        v = c[2] or {}
        return (v["keyframes"][-1] if "keyframes" in v else v)["attr"][key]
    for ch in ("cm-r", "cm-b"):
        off = [c for c in g if str(c[1]).startswith("#cm-rgb feOffset") and ch in str(c[1]) and c[3] >= 4 - 1e-9]
        assert off, ch
        vals = [last_attr(c, "dx") for c in off if end(c) < 4.6 - 1e-9]
        assert len(set(vals)) >= 4 and max(abs(v) for v in vals) == pytest.approx(18, abs=0.01), (ch, vals)
        final = max(off, key=end)
        assert end(final) == pytest.approx(4.6) and last_attr(final, "dx") == 0, (ch, final)
    shakes = [c for c in g if c[1] == "#shake" and c[0] == "to" and "keyframes" in (c[2] or {}) and c[3] == 4]
    assert shakes and any(abs(k["x"]) > 3 for k in shakes[0][2]["keyframes"]) and shakes[0][2]["keyframes"][-1]["x"] == 0
    assert end(shakes[0]) == pytest.approx(4.6, abs=0.04)
    assert d["g"] == d["g2"]                                                          # deterministic
    w = d["w"]
    filt = [(c[3], c[2]["filter"]) for c in w if c[1] == "#split" and "filter" in (c[2] or {})]
    assert (4, "url(#cm-wave)") in filt and (4.6, "none") in filt
    disp = [c for c in w if str(c[1]).startswith("#cm-wave feDisplacementMap") and c[3] >= 4 - 1e-9]
    assert disp and end(max(disp, key=end)) == pytest.approx(4.6) and last_attr(max(disp, key=end), "scale") == 0
    assert max(last_attr(c, "scale") for c in w if str(c[1]).startswith("#cm-wave feDisplacementMap")
               and c[0] == "fromTo") == 0 and any(c[0] == "fromTo" for c in disp)
    assert not any(str(c[1]).startswith("#cm-") or (c[1] == "#split" and "filter" in (c[2] or {})) for c in d["none"])
    assert not any(c[1] == "#shake" and "scale" in (c[2] or {}) for c in d["none"])
    punch = [c for c in g if c[1] == "#shake" and c[0] == "fromTo" and "scale" in (c[2] or {})]
    assert punch and punch[0][3] == 4 and punch[0][2]["scale"] == 1                   # the A-roll punches in, back to 1
    big = _glitch_calls({"b": {**base, "glitch": [[4, 0.6, "glitch", 42]]}})["b"]       # amp from the build (16:9)
    dx = [abs(c[2]["attr"]["dx"]) for c in big if str(c[1]).startswith("#cm-rgb feOffset.cm-") and c[0] == "set"]
    assert max(dx) == 42


# topic-change in a DOM harness: the real effect script with a recording tl; the clock is seeked by hand
_ONE_EL = """const m = %(markup)s.match(/class="([^"]+)"/);
if (m) root.appendChild(new El("div")).className = m[1];"""
# the whole markup as a tree (tags with an optional class; text placeholders already filled in)
_TREE = """{ const stack = [root];
  for (const [, close, tag, cls, text] of %(markup)s.matchAll(/<(\\/?)(\\w+)(?:\\s+class="([^"]*)")?[^>]*>|([^<]+)/g)) {
    if (text !== undefined) { stack[stack.length - 1].textContent = text; continue; }
    if (close) { stack.pop(); continue; }
    const e = stack[stack.length - 1].appendChild(new El(tag)); if (cls) e.className = cls; stack.push(e);
  } }"""
assert _ONE_EL in DOM
TOPIC = DOM.split("const out = {};")[0].replace(_ONE_EL, _TREE) + """
const res = [];
for (const t of %(times)s) {
  seek(t);
  res[res.length] = root.querySelectorAll(".tc-rgb").map((e) => ({ text: e.textContent, tr: e.style.transform || "" }));
}
console.log(JSON.stringify(res));
"""


def _topic(params: dict, times: list) -> list:
    from cutmate.build import _sections
    sec = _sections(plugin_root() / "themes" / "clean" / "components" / "custom" / "topic-change.html")
    markup = sec.get("markup", "").replace("{{title}}", params.get("title", ""))
    js = TOPIC.replace("%(times)s", json.dumps(times)) % {
        "fx": json.dumps(str(web_dir() / "effects.js")), "markup": json.dumps(markup),
        "params": json.dumps(params), "script": sec["script"], "probes": "[]"}
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def _offset(tr: str) -> float:
    nums = [abs(float(v)) for v in re.findall(r"-?[\d.]+(?=px)", tr)]
    return max(nums) if nums else 0.0


@pytest.mark.parametrize("style", ["glitch", "wave"])
def test_topic_change_title_resolves(style):
    """The title (three RGB copies) is still scrambled and split at P.at + 0.1 and final, every copy at offset 0, by
    P.at + 0.7."""
    title = "Druga sprawa: koszty"
    P = {"title": title, "kicker": "ROZDZIAŁ 02", "style": style, "at": 0.3, "end": 1.9, "dur": 1.9, "w": 1080,
         "h": 1920, "lang": "pl", "caption_band": [1295, 1455]}
    d = _topic(P, [0.4, 1.0, 1.4])
    early, final, hold = d
    assert len(early) == 3
    assert all(c["text"] != title for c in early), early
    assert max(_offset(c["tr"]) for c in early) >= 4, early
    assert all(c["text"] == title for c in final + hold), final
    assert all(_offset(c["tr"]) == 0 for c in final + hold), final


# kinetic-word's pure helpers (window.CutmateFX.wow, in effects.js)
KINETIC = """
global.window = {};
require(%s);
const W = window.CutmateFX.wow;
console.log(JSON.stringify((function () { %s })()));
"""


def test_kinetic_word_targets():
    """gridStart: n points of a centred grid inside the frame (cols = ceil(sqrt(n·W/H))); assignTargets: n targets from
    the glyph points, the same for the same seed, another order for another seed, every one a glyph point (inside the
    text box); repeats wrap when n > points."""
    d = _node(KINETIC, json.dumps(str(web_dir() / "effects.js")), """
      const pts = [];
      for (let y = 800; y <= 1000; y += 10) for (let x = 100; x <= 980; x += 10) if ((x + y) % 30) pts.push([x, y]);
      return { grid: W.gridStart(600, 1080, 1920), grid169: W.gridStart(600, 1920, 1080), pts,
               a: W.assignTargets(pts, 600, 7), b: W.assignTargets(pts, 600, 7), c: W.assignTargets(pts, 600, 8),
               few: W.assignTargets(pts.slice(0, 50), 600, 7) };
    """)
    for grid, (w, h) in ((d["grid"], (1080, 1920)), (d["grid169"], (1920, 1080))):
        assert len(grid) == 600
        assert all(0 <= x <= w and 0 <= y <= h for x, y in grid)
        xs, ys = sorted({round(x, 3) for x, _ in grid}), sorted({round(y, 3) for _, y in grid})
        assert len(xs) == math.ceil(math.sqrt(600 * w / h))                          # cols = ceil(sqrt(n·W/H))
        cx, cy = sum(x for x, _ in grid) / 600, sum(y for _, y in grid) / 600
        assert abs(cx - w / 2) < w * 0.03 and abs(cy - h / 2) < h * 0.05            # centred
    assert d["a"] == d["b"] and d["a"] != d["c"] and len(d["a"]) == 600
    pts = {tuple(p) for p in d["pts"]}
    assert all(tuple(p) in pts for p in d["a"])                                      # inside the text box
    assert len({tuple(p) for p in d["a"]}) == min(600, len(pts))
    assert len(d["few"]) == 600 and len({tuple(p) for p in d["few"]}) == 50           # repeats wrap


def test_kinetic_word_lands_on_its_impact():
    """The word lands 1.0 s after P.at (index.json impact) whatever the span (>= 2.5 s), or on P.hit_at (a hit anchor on
    the spoken word) with the <= 1 s build-up just before it; the shatter takes the end."""
    d = _node(KINETIC, json.dumps(str(web_dir() / "effects.js")), """
      const b = (o) => W.kineticBeats(o);
      return { a: b({ at: 0.3, end: 3.8 }), long: b({ at: 0.3, end: 6.3 }), hit: b({ at: 0.3, end: 3.8, hit_at: 2.1 }),
               early: b({ at: 0.3, end: 3.8, hit_at: 0.5 }), late: b({ at: 0.3, end: 3.8, hit_at: 3.7 }),
               short: b({ at: 0, end: 2.0 }) };
    """)
    assert d["a"]["land"] == pytest.approx(1.3) and d["a"]["t0"] == pytest.approx(0.3) and d["a"]["pre"] == pytest.approx(1.0)
    assert d["long"]["land"] == pytest.approx(1.3) and d["a"]["shatter"] == pytest.approx(3.32)
    assert d["hit"]["land"] == pytest.approx(2.1) and d["hit"]["t0"] == pytest.approx(1.1)
    assert d["early"]["land"] == pytest.approx(0.9) and d["early"]["pre"] == pytest.approx(0.6)
    assert d["late"]["land"] == pytest.approx(2.8)                                    # room for the hold + shatter
    assert d["short"]["k"] == pytest.approx(0.8) and d["short"]["land"] == pytest.approx(0.8)


def test_kinetic_word_numbers_take_the_number_font():
    """A word with a digit is drawn in the theme's --font-num (pixel-pill: Pixelify's 5 reads as S, -75% became -7S%),
    other words (and themes without --font-num) in --font-display."""
    d = _node(KINETIC, json.dumps(str(web_dir() / "effects.js")), """
      const f = W.kineticFamily;
      return { num: f("-75%", "Pixelify Sans", "Press Start 2P"), word: f("ZA DARMO", "Pixelify Sans", "Press Start 2P"),
               none: f("+300%", "Inter", ""), unset: f("+300%", "Inter", null) };
    """)
    assert d == {"num": "Press Start 2P", "word": "Pixelify Sans", "none": "Inter", "unset": "Inter"}
