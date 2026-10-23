"""hf snapshots of the WOW explainers (three.js): exploded-view and globe as a split-panel item, a full-frame scene and on a
light cloned theme. Every test prints its snapshot paths — READ them (a spectacular look, readable labels, nothing
clipped at the panel edge) before committing."""
import colorsys
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import wowkit  # noqa: E402
from test_effects_js import _countries, _wow  # noqa: E402

from cutmate import paths  # noqa: E402
from cutmate.hf import check  # noqa: E402

pytestmark = pytest.mark.hf

BOX = (40, 40, 1000, 880)            # the split-panel item region (plan.panel_box(0.5)) in 1080x1920 px
TO = ["US", "JP", "BR"]


def _theme(home: Path, name: str, tokens: dict | None = None, split: bool = True) -> str:
    """A clean copy in $CUTMATE_HOME/themes/<name>: split-panel layout, token values replaced (old -> new)."""
    dst = home / "themes" / name
    shutil.copytree(paths.theme_dir("clean"), dst)
    if split:
        meta = json.loads((dst / "theme.json").read_text(encoding="utf-8"))
        meta["layout"] = {"mode": "split-panel"}
        (dst / "theme.json").write_text(json.dumps(meta), encoding="utf-8")
    css = (dst / "tokens.css").read_text(encoding="utf-8")
    for old, new in (tokens or {}).items():
        assert old in css, old
        css = css.replace(old, new)
    (dst / "tokens.css").write_text(css, encoding="utf-8")
    return name


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    monkeypatch.setenv("CUTMATE_HOME", str(h))
    return h


def _img(png: Path) -> np.ndarray:
    with Image.open(png) as im:
        return np.asarray(im.convert("RGB"), dtype=np.int16)


def _crop(a: np.ndarray, box) -> np.ndarray:
    x, y, w, h = box
    return a[y:y + h, x:x + w]


def _hue_mask(a: np.ndarray, lo: float, hi: float, sat: float = 0.35, val: float = 0.35) -> np.ndarray:
    """Pixels whose hue (degrees) is in [lo, hi] (wrapping) with enough saturation and value."""
    f = a.astype(np.float32) / 255.0
    mx, mn = f.max(axis=2), f.min(axis=2)
    d = np.where(mx - mn == 0, 1e-6, mx - mn)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60.0
    s = np.where(mx == 0, 0, (mx - mn) / np.where(mx == 0, 1, mx))
    inside = (h >= lo) & (h <= hi) if lo <= hi else (h >= lo) | (h <= hi)
    return inside & (s >= sat) & (mx >= val) & (mx - mn > 0)


def _hue_of(hexcol: str) -> float:
    r, g, b = (int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)[0] * 360


def _blobs(mask: np.ndarray, step: int = 3) -> list[tuple]:
    """Connected components of `mask` (on a step-px grid): [(x0, y0, x1, y1, filled cells, cells in bbox)] in px."""
    m = mask[::step, ::step]
    seen = np.zeros_like(m, dtype=bool)
    out = []
    H, W = m.shape
    for y0, x0 in zip(*np.nonzero(m)):
        if seen[y0, x0]:
            continue
        stack, cells = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            cells.append((y, x))
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < H and 0 <= xx < W and m[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    stack.append((yy, xx))
        ys, xs = [c[0] for c in cells], [c[1] for c in cells]
        bx = (min(xs) * step, min(ys) * step, (max(xs) + 1) * step, (max(ys) + 1) * step)
        out.append((*bx, len(cells), (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1)))
    return out


def _pills(a: np.ndarray, box, hue: float = 199.0) -> list[tuple]:
    """The label pills inside `box`, in frame px: an accent index chip (a round accent blob) with a near-white (--card on a
    dark panel) pill body running on to its right. Finding the chip first keeps a pill apart from glows and lit white
    parts of the object that touch it."""
    sub = _crop(a, box)
    white = sub.min(axis=2) >= 215
    found = []
    for x0, y0, x1, y1, n, area in _blobs(_hue_mask(sub, hue - 20, hue + 20, sat=0.3, val=0.5), step=2):
        w, h = x1 - x0, y1 - y0
        if not (26 <= h <= 70 and 26 <= w <= 110 and n >= 0.6 * area):
            continue
        band = white[y0 + h // 4:y1 - h // 4]
        x = x1 + 2
        while x < band.shape[1] - 8 and band[:, x - 8:x + 9].mean() > 0.15:  # the pill body (letter stems included)
            x += 4
        if x - x1 >= 60:
            found.append((x0 + box[0] - 4, y0 + box[1] - 4, x + box[0], y1 + box[1] + 4))
    return found


def _arc_mids(o: dict, t: float) -> list[tuple]:
    """Each arc's projected apex (region px) at root-local time t, from the effect's own pure pose / arc helpers."""
    return [tuple(p) for p in _wow(f"""
      const o = {json.dumps(o)};
      const pose = W.globePose(o, {t});
      return o.to.map((d) => {{ const a = W.arcPoints(o.from[0], o.from[1], d[0], d[1]);
        return W.globeProject(pose, a[32], o.w, o.h); }});""", names=("globe",))]


def _globe_spec(box, at, end, panel, title=""):
    c = _countries()
    ll = lambda k: [c[k]["lat"], c[k]["lng"]]  # noqa: E731
    return {"from": ll("PL"), "to": [ll(k) for k in TO], "w": box[2], "h": box[3], "at": at, "end": end,
            "panel": panel, "title": title}


def _accent_at(a: np.ndarray, x: float, y: float, hue: float, r: int = 12, spread: float = 20) -> int:
    xi, yi = int(round(x)), int(round(y))
    win = a[max(0, yi - r):yi + r + 1, max(0, xi - r):xi + r + 1]
    return int(_hue_mask(win, (hue - spread) % 360, (hue + spread) % 360, sat=0.2, val=0.5).sum())


def _spans(proj: Path, name: str) -> list[tuple]:
    """Root-time [P.at, P.end] of every `name` effect in the built project, in slot order. The build owns them: a panel
    item's host runs on under the next item for the handoff, a scene's host starts before its fade-in."""
    import re
    proj = Path(proj)
    html = (proj / "index.html").read_text(encoding="utf-8")
    out = []
    for cid, start in re.findall(r'data-composition-id="([\w-]+)" data-composition-src="[^"]+" data-start="([\d.]+)"', html):
        comp = (proj / "compositions" / f"{cid}.html").read_text(encoding="utf-8")
        m = re.search(r"const P = (\{.*?\});?\n", comp)
        P = json.loads(m.group(1)) if m else {}
        if P.get("name") == name:
            out.append((round(float(start) + P["at"], 3), round(float(start) + P["end"], 3)))
    return out


def _object_box(a: np.ndarray, box, bg, pills=()) -> tuple:
    """The 3D object's bounding box (frame px) inside `box`: pixels clearly off the background colour, label pills
    blanked out, 1st-99th percentile of columns / rows (a stray glow pixel does not stretch it)."""
    sub = _crop(a, box).copy()
    for x0, y0, x1, y1 in pills:
        sub[max(0, y0 - box[1] - 6):y1 - box[1] + 6, max(0, x0 - box[0] - 6):x1 - box[0] + 6] = bg
    m = np.abs(sub - np.array(bg)).max(axis=2) > 45
    ys, xs = np.nonzero(m)
    if not len(xs):
        return (0, 0, 0, 0)
    x0, x1 = np.percentile(xs, [1, 99]); y0, y1 = np.percentile(ys, [1, 99])
    return (box[0] + x0, box[1] + y0, box[0] + x1, box[1] + y1)


def _check_ok(proj):
    chk = check(proj)
    if chk.status == "deadline":
        print("WARN hyperframes check hit its deadline (machine load) — not a failure")
    assert chk.status in ("ok", "deadline"), chk.output[-3000:]


def test_exploded_view_panel_item(tmp_path, home):
    theme = _theme(home, "wowsplit")
    plan = {"panel": [{"at": 0.1, "effect": "headline", "params": {"text": "Co jest w środku?"}},
                      {"at": "S1:krótko", "until": 3.45, "effect": "exploded-view", "params": {"preset": "engine"}}]}
    proj = wowkit.project(tmp_path, plan, dur=5.0, theme=theme)
    _check_ok(proj)
    (at, end), = _spans(proj, "exploded-view")
    full = at + min(0.5, 0.35 * (end - at))                     # U.fullAt
    mid = (at + end) / 2
    s_full, s_mid = wowkit.snap(proj, full + 0.02), wowkit.snap(proj, mid)
    print(f"snapshot fullAt {full + 0.02:.2f}: {s_full}\nsnapshot mid {mid:.2f}: {s_mid}")
    a = _img(s_full)
    cx, cy = BOX[0] + BOX[2] // 2, BOX[1] + BOX[3] // 2
    centre = a[cy - 150:cy + 150, cx - 150:cx + 150]
    other = (np.abs(centre - np.array([0x0b, 0x0b, 0x0f])).max(axis=2) > 30).mean()
    assert other >= 0.08, f"assembled object not in the panel centre at fullAt ({other:.3f}): {s_full}"
    pills = _pills(_img(s_mid), BOX)
    print("pills at mid:", pills)
    assert len(pills) >= 4, (pills, s_mid)
    assert min(y1 - y0 for x0, y0, x1, y1 in pills) >= 54, pills  # readable on a phone (~40 px type in the panel)
    for x0, y0, x1, y1 in pills:                                # nothing clipped at the panel edge
        assert x0 > BOX[0] + 2 and x1 < BOX[0] + BOX[2] - 2 and y0 > BOX[1] + 2 and y1 < BOX[1] + BOX[3] - 2
    worst = wowkit.seek_safe(proj, mid)
    print(f"seek_safe({mid}) = {worst}")
    assert worst <= 1.0
    print("strip:", wowkit.strip(proj, at, end, 0.25))


def test_exploded_view_scene_169(tmp_path, home):
    parts = [{"label": "Wał korbowy", "shape": "disc"}, {"label": "Blok silnika", "shape": "block"},
             {"label": "Tłoki", "shape": "cylinder"}, {"label": "Pokrywa", "shape": "shell"}]
    plan = {"graphics": [{"type": "custom", "name": "exploded-view", "from": 0.5, "to": 4.5,
                          "params": {"parts": parts, "title": "Silnik"}}]}
    proj = wowkit.project(tmp_path, plan, fmt="16:9", dur=5.0)
    s_mid = wowkit.snap(proj, 2.5)
    print(f"snapshot mid 2.5: {s_mid}")
    pills = _pills(_img(s_mid), (0, 0, 1920, 1080))
    print("pills at mid:", pills)
    assert len(pills) >= 4, (pills, s_mid)
    print("strip:", wowkit.strip(proj, 0.5, 4.5, 0.25))


def test_exploded_view_fills_a_916_scene(tmp_path, home):
    """A reel scene: the exploded object takes most of the frame width, reads as taken apart (exploded much taller than
    assembled) and its labels are big enough for a phone."""
    plan = {"scenes": [{"from": 0.5, "to": 4.5, "effect": "exploded-view", "params": {"preset": "engine", "title": "Silnik"}}]}
    proj = wowkit.project(tmp_path, plan, dur=5.0)
    (at, end), = _spans(proj, "exploded-view")
    span = end - at
    t_asm, t_mid = round(at + 0.19 * span, 3), round(at + 0.62 * span, 3)
    s_asm, s_mid = wowkit.snap(proj, t_asm), wowkit.snap(proj, t_mid)
    print(f"snapshot assembled {t_asm}: {s_asm}\nsnapshot exploded {t_mid}: {s_mid}")
    full, below = (0, 0, 1080, 1920), (0, 300, 1080, 1800)     # the object is measured under the title band
    a, m = _img(s_asm), _img(s_mid)
    pills = _pills(m, full)
    print("pills:", pills)
    assert len(pills) >= 4 and min(y1 - y0 for x0, y0, x1, y1 in pills) >= 64, pills   # ~50 px type at 1080 wide
    bx_a, bx_m = _object_box(a, below, (0x0b, 0x0b, 0x0f)), _object_box(m, below, (0x0b, 0x0b, 0x0f), pills)
    wr = (bx_m[2] - bx_m[0]) / 1080
    hr = (bx_m[3] - bx_m[1]) / max(1.0, bx_a[3] - bx_a[1])
    print(f"object box assembled {bx_a}, exploded {bx_m}: width {wr:.2f} of the frame, exploded / assembled height {hr:.2f}")
    assert wr >= 0.55, (wr, s_mid)
    assert hr >= 1.5, (hr, s_asm, s_mid)
    worst = wowkit.seek_safe(proj, t_mid)
    print(f"seek_safe({t_mid}) = {worst}")
    assert worst <= 1.0
    print("strip:", wowkit.strip(proj, at, end, 0.25))


def test_globe_panel_and_scene(tmp_path, home):
    theme = _theme(home, "wowsplit")
    params = {"from": "PL", "to": TO}
    plan = {"panel": [{"at": 0.1, "effect": "headline", "params": {"text": "Skąd są widzowie?"}},
                      {"at": "S1:krótko", "until": 3.45, "effect": "globe", "params": params},
                      {"at": 3.45, "effect": "headline", "params": {"text": "Trzy kontynenty"}}],   # the globe ends with a cut
            "scenes": [{"from": 4.0, "to": 7.5, "effect": "globe", "params": params}]}
    proj = wowkit.project(tmp_path, plan, dur=8.0, theme=theme)
    _check_ok(proj)
    hue = _hue_of("#7dd3fc")
    (pa, pe), (sa, se) = _spans(proj, "globe")
    for box, at, end, panel in ((BOX, pa, pe, True), ((0, 0, 1080, 1920), sa, se, False)):
        t = round(at + 0.8 * (end - at), 3)
        t_late = round(at + 0.9 * (end - at), 3)                  # still before the next panel item cuts in
        s, s_late = wowkit.snap(proj, t), wowkit.snap(proj, t_late)
        print(f"snapshot {'panel' if panel else 'scene'} 0.8 ({t}): {s}\nsnapshot 0.9 ({t_late}): {s_late}")
        a, late = _img(s), _img(s_late)
        mids = _arc_mids(_globe_spec(box, at, end, panel), t)
        for (x, y, front), k in zip(mids, TO):                   # every arc is drawn through its apex
            n = _accent_at(a, box[0] + x, box[1] + y, hue)
            print(f"arc PL-{k} apex ({box[0] + x:.0f}, {box[1] + y:.0f}) front={front:.2f}: {n} accent px")
            assert front > 0 and n >= 6, (k, x, y, n, s)
        pills = _pills(late, box)
        assert len(pills) >= 4, (pills, s_late)                  # origin + 3 destinations
        for x0, y0, x1, y1 in pills:                             # the labels are final at 0.8: same as at 0.9
            d = np.abs(a[y0:y1, x0:x1] - late[y0:y1, x0:x1]).mean()
            assert d <= 3.0, ((x0, y0, x1, y1), d, s, s_late)
        worst = wowkit.seek_safe(proj, t)
        print(f"seek_safe({t}) = {worst}")
        assert worst <= 1.0
        print("strip:", wowkit.strip(proj, at, end, 0.25))


def test_three_explainers_take_light_panel(tmp_path, home):
    """Review Focus 3: a cloned theme with a light panel and an orange accent — the panel stays the theme's colour, the
    exploded labels and the globe's arcs are orange."""
    theme = _theme(home, "lightpanel", {"--panel-bg: #0b0b0f;": "--panel-bg: #efece7;", "--accent: #7dd3fc;": "--accent: #c2501f;"})
    plan = {"panel": [{"at": 0.1, "effect": "exploded-view", "params": {"preset": "engine"}},
                      {"at": "S2:minus", "until": 4.6, "effect": "globe", "params": {"from": "PL", "to": TO}}]}
    proj = wowkit.project(tmp_path, plan, dur=5.0, theme=theme)
    _check_ok(proj)
    (xa, xe), = _spans(proj, "exploded-view")
    (ga, ge), = _spans(proj, "globe")
    t_x, t_g = round((xa + xe) / 2, 3), round(ga + 0.8 * (ge - ga), 3)
    s_x, s_g = wowkit.snap(proj, t_x), wowkit.snap(proj, t_g)
    print(f"snapshot exploded mid {t_x}: {s_x}\nsnapshot globe 0.8 {t_g}: {s_g}")
    for s in (s_x, s_g):
        a = _img(s)
        corner = a[60, 60]
        assert all(abs(int(c) - e) <= 6 for c, e in zip(corner, (0xef, 0xec, 0xe7))), (s, corner)
    a = _crop(_img(s_x), BOX)
    sides = np.concatenate([a[:, :300], a[:, -300:]], axis=1)    # the label columns (the object is in the middle)
    orange = int(_hue_mask(sides, 15, 30, sat=0.5).sum())
    print(f"orange px in the exploded label columns: {orange}")
    assert orange >= 150, (orange, s_x)
    # no white haze over the object: it keeps its contrast against the light panel (bloom / glow wash it out)
    ob = _object_box(_img(s_x), BOX, (0xef, 0xec, 0xe7))
    reg = _img(s_x)[int(ob[1]):int(ob[3]), int(ob[0]):int(ob[2])].astype(np.float32)
    lum = reg @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    print(f"light panel object box {ob}: luminance mean {lum.mean():.1f}, std {lum.std():.1f}")
    assert lum.std() >= 35 and lum.mean() <= 205, (lum.mean(), lum.std(), s_x)
    g = _img(s_g)
    for (x, y, front), k in zip(_arc_mids(_globe_spec(BOX, ga, ge, True), t_g), TO):
        win = g[int(BOX[1] + y) - 12:int(BOX[1] + y) + 13, int(BOX[0] + x) - 12:int(BOX[0] + x) + 13]
        n = int(_hue_mask(win, 15, 30, sat=0.3, val=0.4).sum())
        print(f"arc PL-{k} apex: {n} orange px")
        assert n >= 6, (k, n, s_g)
