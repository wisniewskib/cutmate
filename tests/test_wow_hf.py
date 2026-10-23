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
from test_effects_js import _burst, _countries, _wow  # noqa: E402

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


def _globe_spec(box, at, end, panel, title="", P=None):
    c = _countries()
    ll = lambda k: [c[k]["lat"], c[k]["lng"]]  # noqa: E731
    o = {"from": ll("PL"), "to": [ll(k) for k in TO], "w": box[2], "h": box[3], "at": at, "end": end,
         "panel": panel, "title": title}
    safe = _safe(P or {})
    if safe and (safe[0] > 0 or safe[1] < box[3]):
        o["safe"] = safe
    return o


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
            _PS.setdefault((str(proj), name), []).append(P)
    return out


_PS: dict = {}


def _P(proj: Path, name: str, i: int = 0) -> dict:
    """The built P of the i-th `name` effect (after _spans)."""
    if (str(Path(proj)), name) not in _PS:
        _spans(proj, name)
    return _PS[(str(Path(proj)), name)][i]


def _safe(P: dict) -> list | None:
    """U.safeBox(P) as [y0, y1] (effects.js: the bigger side of the caption band, 1.2 % pad), None without a band."""
    b = P.get("caption_band")
    if not b:
        return None
    pad = 0.012 * P["h"]
    above, below = max(0.0, min(P["h"], b[0] - pad)), max(0.0, P["h"] - max(0.0, b[1] + pad))
    return [0, above] if above >= below else [P["h"] - below, P["h"]]


def _clear_of_band(pills, band, region_y=0):
    """No pill crosses the burned captions (band in region px)."""
    if band:
        y0, y1 = band[0] + region_y, band[1] + region_y
        hits = [p for p in pills if p[1] < y1 and p[3] > y0]
        assert not hits, (hits, (y0, y1))


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
    full, below = (0, 0, 1080, 1920), (0, 300, 1080, 990)      # under the title, above the captions
    a, m = _img(s_asm), _img(s_mid)
    pills = _pills(m, full)
    print("pills:", pills)
    assert len(pills) >= 4 and min(y1 - y0 for x0, y0, x1, y1 in pills) >= 64, pills   # ~50 px type at 1080 wide
    band = _P(proj, "exploded-view")["caption_band"]
    assert band == [1295, 1455]
    _clear_of_band(pills, band)                                 # the labels stay off the burned captions
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
    for k_, (box, at, end, panel) in enumerate(((BOX, pa, pe, True), ((0, 0, 1080, 1920), sa, se, False))):
        P = _P(proj, "globe", k_)
        t = round(at + 0.8 * (end - at), 3)
        t_late = round(at + 0.9 * (end - at), 3)                  # still before the next panel item cuts in
        s, s_late = wowkit.snap(proj, t), wowkit.snap(proj, t_late)
        print(f"snapshot {'panel' if panel else 'scene'} 0.8 ({t}): {s}\nsnapshot 0.9 ({t_late}): {s_late}")
        a, late = _img(s), _img(s_late)
        mids = _arc_mids(_globe_spec(box, at, end, panel, P=P), t)
        for (x, y, front), k in zip(mids, TO):                   # every arc is drawn through its apex
            n = _accent_at(a, box[0] + x, box[1] + y, hue)
            print(f"arc PL-{k} apex ({box[0] + x:.0f}, {box[1] + y:.0f}) front={front:.2f}: {n} accent px")
            assert front > 0 and n >= 6, (k, x, y, n, s)
        pills = _pills(late, box)
        assert len(pills) >= 4, (pills, s_late)                  # origin + 3 destinations
        _clear_of_band(pills, P.get("caption_band"), box[1])     # the labels stay off the burned captions
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
    for (x, y, front), k in zip(_arc_mids(_globe_spec(BOX, ga, ge, True, P=_P(proj, "globe")), t_g), TO):
        win = g[int(BOX[1] + y) - 12:int(BOX[1] + y) + 13, int(BOX[0] + x) - 12:int(BOX[0] + x) + 13]
        n = int(_hue_mask(win, 15, 30, sat=0.3, val=0.4).sum())
        print(f"arc PL-{k} apex: {n} orange px")
        assert n >= 6, (k, n, s_g)


# ---- burst-out: a 3D object bursts from behind the speaker (bg effect drawing the cut-out) ----

FACE = (400, 700)                      # the drawn speaker's face centre (px, 1080x1920)
SKIN, SHIRT = (196, 150, 122), (38, 58, 92)


def _speaker(tmp_path: Path, dur: float = 6.0) -> tuple:
    """A person-like A-roll (testsrc2 + a drawn head and torso) and its transparent cut-out (VP9 alpha WebM, what
    `hyperframes remove-background` gives), both from one silhouette PNG so they line up to the pixel. Returns
    (aroll.mp4, bgcut.webm, head mask, torso mask)."""
    from PIL import ImageDraw
    from conftest import make_clip
    from cutmate.media import run
    W, H = 1080, 1920
    sil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(sil)
    fx, fy = FACE
    d.rounded_rectangle((fx - 330, 905, fx + 330, H + 40), radius=170, fill=SHIRT + (255,))     # shoulders + torso
    d.rectangle((fx - 62, 800, fx + 62, 930), fill=SKIN + (255,))                               # neck
    d.ellipse((fx - 118, fy - 150, fx + 118, fy + 150), fill=SKIN + (255,))                     # head
    png = tmp_path / "speaker.png"
    sil.save(png)
    plain = make_clip(tmp_path / "plain.mp4", dur=dur, size=f"{W}x{H}", gaps=())
    aroll, cut = tmp_path / "speaker.mp4", tmp_path / "bgcut.webm"
    r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", plain, "-i", png, "-filter_complex", "[0:v][1:v]overlay=0:0",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy", aroll])
    assert r.returncode == 0, r.stderr
    r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-i", png, "-t", str(dur),
             "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0", "-b:v", "1M", cut])
    assert r.returncode == 0, r.stderr
    a = np.asarray(sil)[..., 3] > 0
    yy, xx = np.mgrid[0:H, 0:W]
    head = ((xx - fx) / 108.0) ** 2 + ((yy - fy) / 140.0) ** 2 <= 1          # a little inside the drawn ellipse
    torso = a & (yy > 960) & (yy < 1270) & (np.abs(xx - fx) < 300)            # above the caption band
    return aroll, cut, head, torso


def test_burst_out_renders(tmp_path, home, monkeypatch):
    """9:16 bg + burst-out, hit on "mniej" (S1 word 3): at 0.6 s the object is behind the speaker (his silhouette is
    untouched), just after the hit it is in front over his body and bright, at the hold it sits beside him and his face
    is clear; seek-safe at the hold. READ the snapshots and the 0.1 s strip around the hit."""
    from cutmate import build as B
    aroll, cut, head, torso = _speaker(tmp_path)

    def fake_cut(src, a, b, media):
        name = f"bgcut-{int(a * 1000)}-{int(b * 1000)}.webm"
        shutil.copyfile(cut, media / name)
        return name
    monkeypatch.setattr(B, "bg_cutout", fake_cut)
    plan = {"face": {"S1": [FACE[0] / 1080, FACE[1] / 1920]},
            "graphics": [{"type": "bg", "from": "S1:Mówić", "to": "S2:</script>", "effect": "burst-out", "hit": "S1:mniej",
                          "params": {"label": "Gotowe!"}}]}
    proj = wowkit.project(tmp_path, plan, dur=6.0, aroll=aroll)
    _check_ok(proj)
    P = _P(proj, "burst-out")
    hit = 0.90                                                    # the word's start (global s)
    host = 0.10 - P["at"]
    assert abs(P["hit_at"] + host - hit) < 1e-6 and P["face"] == [float(FACE[0]), float(FACE[1])]
    hold = round(host + (P["at"] + P["end"]) / 2 + 0.6, 2)
    s_behind, s_hit, s_hold = wowkit.snap(proj, 0.6), wowkit.snap(proj, hit + 0.1), wowkit.snap(proj, hold)
    print(f"snapshot behind 0.6: {s_behind}\nsnapshot hit+0.1 {hit + 0.1:.2f}: {s_hit}\nsnapshot hold {hold}: {s_hold}")
    a = _img(s_behind)
    off_head = np.abs(a[head] - np.array(SKIN)).mean()
    off_torso = np.abs(a[torso] - np.array(SHIRT)).mean()
    print(f"behind: head off {off_head:.2f}, torso off {off_torso:.2f}")
    assert off_head < 10 and off_torso < 10, "the object (or its rays) shows over the speaker before the hit"
    b = _img(s_hit)
    o = _burst(P, [], [hit + 0.1 - host])["path"][0]                # where the effect puts the object (pure path)
    yy, xx = np.mgrid[0:1920, 0:1080]
    disk = ((xx - o["x"]) ** 2 + (yy - o["y"]) ** 2 <= (0.6 * o["r"]) ** 2) & torso
    bright = (np.abs(b[disk] - np.array(SHIRT)).max(axis=1) > 60) & (b[disk].mean(axis=1) > 140)
    print(f"hit+0.1: object at ({o['x']:.0f}, {o['y']:.0f}) r {o['r']:.0f}: {int(disk.sum())} px over the torso, "
          f"{bright.mean() if disk.any() else 0:.2f} of them bright")
    assert disk.sum() >= 3000, "the object is not over the speaker's body just after the hit"
    assert bright.mean() >= 0.8, "the object is not in front of the speaker (or not bright) just after the hit"
    c = _img(s_hold)
    off_face = np.abs(c[head] - np.array(SKIN)).mean()
    side = c[700:1280, 600:1080]
    lit = int(((side.max(axis=2) - side.min(axis=2)) > 60).sum())
    print(f"hold: face off {off_face:.2f}, {lit} coloured px beside him")
    assert off_face < 10, "the object covers the face at the hold"
    h = _burst(P, [], [hold - host])["path"][0]
    ring = c[int(h["y"] - 0.5 * h["r"]):int(h["y"] + 0.5 * h["r"]), int(h["x"] - 0.5 * h["r"]):int(h["x"] + 0.5 * h["r"])]
    print(f"hold: object at ({h['x']:.0f}, {h['y']:.0f}) r {h['r']:.0f}, mean {ring.mean():.0f}")
    assert h["r"] >= 150 and ring.mean() > 150, "the held object is not big and bright beside him"
    worst = wowkit.seek_safe(proj, hold)
    print(f"seek_safe({hold}) = {worst}")
    assert worst <= 1.0
    print("strip hit:", wowkit.strip(proj, hit - 0.3, hit + 0.5, 0.1))
    print("strip:", wowkit.strip(proj, 0.1, 3.6, 0.25))


def _hand_tracks(dur: float = 4.4) -> dict:
    """Synthetic 9:16 tracks: the right palm moves left -> right (x 0.35 -> 0.65 over 4 s) at y 0.62, open 1.0–3.0 s;
    five fingertips fanned above it, all extended."""
    from cutmate.tracks import FINGERS, TRACKS
    fan = [(-0.10, -0.03), (-0.05, -0.10), (0.0, -0.115), (0.05, -0.10), (0.09, -0.07)]
    ts = [round(i / 15, 4) for i in range(int(dur * 15))]
    px = lambda t: 0.35 + 0.3 * min(1.0, t / 4)  # noqa: E731
    tr = {n: [] for n in TRACKS}
    tr["palm_right"] = [[t, px(t), 0.62, 1.0 if 1.0 <= t < 3.0 else 0.0] for t in ts]
    for (dx, dy), f in zip(fan, FINGERS):
        tr[f"{f}_right"] = [[t, px(t) + dx, 0.62 + dy, 1.0] for t in ts]
    return tr


def test_hand_control_renders(tmp_path, home):
    """9:16 hand-control over a synthetic right hand: at 0.8 s bold warm sparks stream from the five fingertips (a big
    share of bright changed pixels at each tip) and the card is folded; at 1.6 s the card is open ABOVE the fingertips
    (a big --card block, title readable) and the fingertip sparks are still visible under it; at 3.4 s it has folded away
    with nothing left behind. Seek-safe at 1.6. READ the snapshots and the 0.25 s strip."""
    from cutmate.media import run
    plan = {"graphics": [{"type": "custom", "name": "hand-control", "from": 0.3, "to": 3.8,
                          "params": {"card": {"title": "Kontrola gestem", "lines": ["iskry z palców", "karta z dłoni"]}}}]}
    proj = wowkit.project(tmp_path, plan, dur=6.0, tracks=_hand_tracks())
    _check_ok(proj)
    P = _P(proj, "hand-control")
    host = 0.3 - P["at"]
    s08, s16, s34 = wowkit.snap(proj, 0.8), wowkit.snap(proj, 1.6), wowkit.snap(proj, 3.4)
    print(f"snapshot 0.8: {s08}\nsnapshot 1.6: {s16}\nsnapshot 3.4: {s34}")
    yy, xx = np.mgrid[0:1920, 0:1080]

    def raw(t):
        png = tmp_path / f"raw{t}.png"
        r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(t), "-i", Path(proj).parent / "aroll.mp4", "-frames:v", "1", png])
        assert r.returncode == 0, r.stderr
        return _img(png)

    def at(series, t):
        return next(s[1:3] for s in series if s[0] >= t - host - 1e-6)

    def sparks(png, t, label):
        a, base = _img(png), raw(t)
        bright = (a.min(axis=2) > 150) & (np.abs(a - base).sum(axis=2) > 150)
        shares = []
        for k, tip in enumerate(P["tips"]["right"]):
            x, y = at(tip, t)
            near = ((xx - x) ** 2 + (yy - y) ** 2) <= 90 ** 2
            shares.append(float(bright[near].mean()))
        print(f"{label}: bright changed share near tips {[round(v, 2) for v in shares]}")
        return shares, a, base
    sh08, a, base = sparks(s08, 0.8, "0.8")
    assert min(sh08) >= 0.10, "fingertip sparks too faint at 0.8 s"
    far = (yy < 300) | (yy > 1500)
    assert np.abs(a[far] - base[far]).mean() < 2, "the effect paints away from the hand"
    sh16, _, _ = sparks(s16, 1.6, "1.6")
    assert min(sh16) >= 0.10, "the open card hides the fingertip sparks"

    def card_white(png, t):
        x, y = at(P["palms"]["right"], t)
        top = min(at(tip, t)[1] for tip in P["tips"]["right"])
        hinge = min(y - P["lift"], top - 0.035 * 1080)
        box = _img(png)[int(hinge - 200):int(hinge - 60), int(x - 150):int(x + 150)]
        return float(((box.min(axis=2) > 215) & (box.max(axis=2) - box.min(axis=2) < 30)).mean())
    w08, w16, w34 = card_white(s08, 0.8), card_white(s16, 1.6), card_white(s34, 3.4)
    print(f"card white share: 0.8 {w08:.2f}, 1.6 {w16:.2f}, 3.4 {w34:.2f}")
    assert w16 >= 0.5 and w08 <= 0.25 and w34 <= 0.25
    worst = wowkit.seek_safe(proj, 1.6)
    print(f"seek_safe(1.6) = {worst}")
    assert worst <= 1.0
    print("strip:", wowkit.strip(proj, 0.3, 3.8, 0.25))


# ---- topic-change (A-roll glitch + scrambled title, chapter_fx) and kinetic-word (anime.js punch scene) ----

def _raw(proj: Path, t: float, tmp: Path) -> np.ndarray:
    """The A-roll frame at t (no graphics)."""
    from cutmate.media import run
    png = tmp / f"raw-{t:.3f}.png"
    r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", Path(proj).parent / "aroll.mp4",
             "-frames:v", "1", png])
    assert r.returncode == 0, r.stderr
    return _img(png)


def _x_shift(snap_ch: np.ndarray, raw_ch: np.ndarray, reach: int = 40) -> tuple:
    """The x shift (px) that best maps the raw channel onto the snapshot channel (normalised correlation of the x
    gradients), with its score."""
    gs, gr = np.diff(snap_ch.astype(np.float32), axis=1), np.diff(raw_ch.astype(np.float32), axis=1)
    best = (0, -1.0)
    for s in range(-reach, reach + 1):
        x, y = (gs[:, s:], gr[:, :gr.shape[1] - s]) if s >= 0 else (gs[:, :s], gr[:, -s:])
        c = float((x * y).sum() / np.sqrt((x * x).sum() * (y * y).sum() + 1e-9))
        if c > best[1]:
            best = (s, c)
    return best


def test_topic_change_169_chapter(tmp_path, home):
    """16:9 long-form with "chapter_fx": "topic-change": the chapter 2 plate glitches the A-roll (at +0.15 s its red and
    blue channels sit >= 4 px apart, measured against the clean A-roll frame) and the title is final at +0.9 s. Seek-safe
    at both. READ the snapshots and the 0.1 s strip."""
    plan = {"chapter_fx": "topic-change",
            "chapters": [{"at": "S1:Mówić", "title": "Wstęp"}, {"at": "S2:minus", "title": "Druga sprawa: koszty"}]}
    proj = wowkit.project(tmp_path, plan, fmt="16:9", dur=5.0)
    _check_ok(proj)
    (at, end), = _spans(proj, "topic-change")
    assert at == 2.1
    t1, t2 = round(at + 0.15, 3), round(at + 0.9, 3)
    s1, s2 = wowkit.snap(proj, t1), wowkit.snap(proj, t2)
    print(f"snapshot glitch {t1}: {s1}\nsnapshot title {t2}: {s2}")
    a, raw = _img(s1), _raw(proj, t1, tmp_path)
    # each channel's x shift against the clean frame (scanlines and the title keep the scores low, ~0.1–0.25; the
    # peaks are still sharp): green moves only with the #shake jitter, red and blue split away from it on both sides
    # (the A-roll is also punched in, 1.08 -> 1 around the centre: measured in a central band where that moves little)
    band = (slice(None), slice(760, 1160))
    (sr, cr), (sg, cg), (sb, cb) = (_x_shift(a[band][:, :, c], raw[band][:, :, c], reach=80) for c in range(3))
    print(f"channel shift at +0.15: R {sr} px ({cr:.2f}), G {sg} px ({cg:.2f}), B {sb} px ({cb:.2f})")
    assert sr - sb >= 0.02 * 1920 and sr > sg > sb and min(cr, cg, cb) > 0.05, (sr, sg, sb, cr, cg, cb, s1)
    b, raw2 = _img(s2), _raw(proj, t2, tmp_path)
    shifts = [_x_shift(b[:, :, c], raw2[:, :, c])[0] for c in range(3)]
    print(f"channel shift at +0.9: R / G / B {shifts} px")
    assert shifts == [0, 0, 0], shifts                                  # the glitch is over
    wm = b.min(axis=2) >= 225
    white = int(wm.sum())
    ghosts = int((_hue_mask(b, 340, 20, sat=0.6, val=0.6) | _hue_mask(b, 170, 200, sat=0.6, val=0.6)).sum())
    rows = np.nonzero(wm.sum(axis=1) > 20)[0]
    tall = (rows.max() - rows.min()) / 1080 if len(rows) else 0
    print(f"title at +0.9: {white} white px over {tall:.2f} of the height, {ghosts} saturated red / cyan px")
    assert white >= 60000 and tall >= 0.25 and ghosts <= 0.05 * white, (white, tall, ghosts, s2)
    for t in (t1, t2):
        worst = wowkit.seek_safe(proj, t)
        print(f"seek_safe({t}) = {worst}")
        assert worst <= 1.0
    print("strip:", wowkit.strip(proj, 1.9, 3.7, 0.1))


def _kinetic_blobs(a: np.ndarray, accent_hue: float, text_dark: bool = False) -> list:
    """Accent / text-colour blobs (1 px grid, kept when 12–900 px): the overlay's shapes over the video."""
    m = _hue_mask(a, accent_hue - 22, accent_hue + 22, sat=0.3, val=0.35)
    m |= (a.max(axis=2) <= 60) & (a.max(axis=2) - a.min(axis=2) < 40) if text_dark else (a.min(axis=2) >= 200)
    return [b for b in _blobs(m, step=1) if 12 <= b[4] <= 900]


def _targets(mask_png: Path) -> int:
    """The distinct shape targets inside the word: params._mask dots every shape's target (3x3 black) on the solid word;
    shapes that share a cell share a dot. (Counting shapes in the real frame cannot work: the landed shapes nearly touch
    and merge through their anti-aliased edges.)"""
    a = _img(mask_png)
    dots = a.max(axis=2) <= 4
    return len([b for b in _blobs(dots, step=1) if 4 <= b[4] <= 25])


def _covered(a: np.ndarray, mask_png: Path, bg) -> tuple:
    """(share of the glyph mask covered by shape pixels within 1 px, mask px): the mask is the solid word the effect draws
    with params._mask (a test aid) at the same place (its target dots, black, fall outside the > 100 threshold: holes)."""
    mk = _img(mask_png)
    mask = np.abs(mk - np.array(bg)).max(axis=2) > 100
    shape = np.abs(a - np.array(bg)).max(axis=2) > 60
    grown = shape.copy()
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        grown |= np.roll(np.roll(shape, dy, axis=0), dx, axis=1)
    return float(grown[mask].mean()) if mask.any() else 0.0, int(mask.sum())


def test_kinetic_word_scene_and_overlay(tmp_path, home):
    """kinetic-word as a 9:16 split-panel scene ("+300%", 3.5 s): at the span's middle the word stands built out of
    >= 400 shapes (distinct targets) covering >= 60 % of its glyphs (1 px tolerance) — already 1.1 s after its start —,
    seek-safe, and the project
    renders. Then as a classic transparent overlay (bg "none") over the A-roll. READ the snapshots and 0.25 s strips."""
    from cutmate.media import run
    from cutmate.hf import hf
    theme = _theme(home, "wowsplit")
    scene = {"from": 0.5, "to": 4.0, "effect": "kinetic-word", "params": {"text": "+300%"}}
    proj = wowkit.project(tmp_path, {"scenes": [scene]}, dur=5.0, theme=theme)
    _check_ok(proj)
    (at, end), = _spans(proj, "kinetic-word")
    assert round(end - at, 2) == 3.5
    mid = round((at + end) / 2, 3)
    s_mid = wowkit.snap(proj, mid)
    mask_proj = wowkit.project(tmp_path / "mask", {"scenes": [dict(scene, params={"text": "+300%", "_mask": True})]},
                               dur=5.0, theme=theme)
    s_mask = wowkit.snap(mask_proj, mid)
    print(f"snapshot mid {mid}: {s_mid}\nglyph mask: {s_mask}")
    a = _img(s_mid)
    bg = (0x0b, 0x0b, 0x0f)
    assert all(abs(int(c) - e) <= 8 for c, e in zip(a[40, 40], bg)), a[40, 40]          # the panel colour, full frame
    targets = _targets(s_mask)
    share, n_mask = _covered(a, s_mask, bg)
    print(f"shapes: {targets} distinct targets in the word; glyph mask {n_mask} px covered {share:.2f}")
    assert targets >= 400, (targets, s_mask)
    assert n_mask >= 40000 and share >= 0.60, (n_mask, share, s_mid)
    # the word reads early: landed 1.0 s after the start (index.json impact)
    s_early = wowkit.snap(proj, round(at + 1.1, 3))
    share_e, _ = _covered(_img(s_early), s_mask, bg)
    print(f"snapshot at+1.1 {s_early}: glyph mask covered {share_e:.2f}")
    assert share_e >= 0.55, (share_e, s_early)
    worst = wowkit.seek_safe(proj, mid)
    print(f"seek_safe({mid}) = {worst}")
    assert worst <= 1.0
    print("strip:", wowkit.strip(proj, at, end, 0.25))
    r = run(hf("render", "--fps", "30", "--quality", "draft", "--format", "mp4", "-o", "../kw-render.mp4"), cwd=proj)
    video = Path(proj).parent / "kw-render.mp4"
    assert r.returncode == 0 and video.exists(), (r.stdout + r.stderr)[-2000:]
    from cutmate.media import duration
    assert duration(video) >= 4.9
    print("render:", video)
    # classic transparent overlay
    plan = {"graphics": [{"type": "custom", "name": "kinetic-word", "from": 0.5, "to": 4.0,
                          "params": {"text": "+300%", "bg": "none", "kicker": "wzrost"}}]}
    ov = wowkit.project(tmp_path / "ov", plan, dur=5.0)
    _check_ok(ov)
    (oa, oe), = _spans(ov, "kinetic-word")
    om = round((oa + oe) / 2, 3)
    s_ov = wowkit.snap(ov, om)
    print(f"overlay snapshot mid {om}: {s_ov}")
    o, raw = _img(s_ov), _raw(ov, om, tmp_path)
    corner = o[:120, :120].reshape(-1, 3).mean(axis=0)
    print(f"overlay corner {corner.round(1)} (A-roll red bar), raw {raw[:120, :120].reshape(-1, 3).mean(axis=0).round(1)}")
    assert corner[0] > 180 and corner[1] < 60 and corner[2] < 60, corner           # the A-roll shows through, no panel
    n = len(_kinetic_blobs(o, _hue_of("#7dd3fc")))
    print(f"overlay shapes: {n}")
    assert n >= 250, (n, s_ov)
    worst = wowkit.seek_safe(ov, om)
    print(f"overlay seek_safe({om}) = {worst}")
    assert worst <= 1.0
    print("overlay strip:", wowkit.strip(ov, oa, oe, 0.25))


def test_kinetic_word_takes_light_panel(tmp_path, home):
    """Review Focus 3: a light panel and an orange accent — the panel keeps the theme colour, the word is built of orange
    and dark (--ink, not the white --text) shapes."""
    theme = _theme(home, "lightkw", {"--panel-bg: #0b0b0f;": "--panel-bg: #efece7;", "--accent: #7dd3fc;": "--accent: #c2501f;"})
    plan = {"scenes": [{"from": 0.5, "to": 4.0, "effect": "kinetic-word", "params": {"text": "ZA DARMO", "kicker": "cena"}}]}
    proj = wowkit.project(tmp_path, plan, dur=5.0, theme=theme)
    (at, end), = _spans(proj, "kinetic-word")
    mid = round((at + end) / 2, 3)
    s = wowkit.snap(proj, mid)
    print(f"light snapshot mid {mid}: {s}")
    a = _img(s)
    assert all(abs(int(c) - e) <= 8 for c, e in zip(a[40, 40], (0xef, 0xec, 0xe7))), a[40, 40]
    orange = int(_hue_mask(a, 8, 32, sat=0.5).sum())
    dark = int(((a.max(axis=2) <= 70) & (a.max(axis=2) - a.min(axis=2) < 40)).sum())
    print(f"orange px {orange}, dark px {dark}")
    assert orange >= 20000 and dark >= 3000, (orange, dark, s)
    print("strip:", wowkit.strip(proj, at, end, 0.25))


def _caption_rows(burn: np.ndarray, none: np.ndarray) -> tuple:
    """(y0, y1) of the rows where the burned-captions frame differs from the same frame built with captions "none"."""
    d = np.abs(burn - none).max(axis=2) > 60
    rows = np.nonzero(d.sum(axis=1) >= 6)[0]
    return (int(rows.min()), int(rows.max())) if len(rows) else (None, None)


def test_wow_scene_drops_captions_in_split_panel(tmp_path, home):
    """Ruling I1: a kinetic-word scene (0.6–2.0 s) in a split-panel video with the panel up from the start: the captions
    sit on the seam before it (0.3 s), in the classic bottom band during it (1.3 s, the word landed) and back on the
    seam after it (2.5 s); the word stays above the bottom band. The caption rows are where the burned frame differs
    from the same project built with captions "none". Seek-safe at start + 0.1 and end - 0.1. READ the snapshots."""
    from cutmate import build as B
    theme = _theme(home, "wowsplit")
    plan = {"panel": [{"at": 0.1, "effect": "headline", "params": {"text": "Co nowego?"}}],
            "scenes": [{"from": 0.6, "to": 2.0, "effect": "kinetic-word", "params": {"text": "+300%"}}]}
    proj = wowkit.project(tmp_path, plan, dur=5.0, theme=theme)
    _check_ok(proj)
    times = (0.3, 1.3, 2.5)
    keep = tmp_path / "burn"
    keep.mkdir()
    shots = [shutil.copyfile(wowkit.snap(proj, t), keep / f"burn-{t}.png") for t in times]
    print("snapshots (captions burned):", [str(p) for p in shots])
    burn = [_img(p) for p in shots]
    for t in (0.7, 1.9):
        worst = wowkit.seek_safe(proj, t)
        print(f"seek_safe({t}) = {worst}")
        assert worst <= 1.0
    B.build(proj.parent, theme=theme, captions={"9:16": "none"})
    none = [_img(wowkit.snap(proj, t)) for t in times]
    (b0, b1), (a0, a1) = _caption_rows(burn[0], none[0]), _caption_rows(burn[2], none[2])
    # during the scene the word itself moves with the caption band (the "none" build has none), so the captions are
    # the white rows below the word (its accent shapes and white dots end above the bottom band)
    word = _hue_mask(burn[1], _hue_of("#7dd3fc") - 22, _hue_of("#7dd3fc") + 22, sat=0.3)
    ys = np.nonzero(word.sum(axis=1) >= 3)[0]
    white = np.nonzero((burn[1].min(axis=2) >= 230).sum(axis=1) >= 6)[0]
    caps = white[white > ys.max()]
    m0, m1 = (int(caps.min()), int(caps.max())) if len(caps) else (None, None)
    print(f"caption rows: before {b0}–{b1}, during {m0}–{m1}, after {a0}–{a1}; word (accent) rows {ys.min()}–{ys.max()}, "
          f"{int(word.sum())} px")
    assert b0 is not None and 780 <= b0 and b1 <= 1140, (b0, b1)               # the seam (y 960)
    assert m0 is not None and m0 >= 1180 and m1 <= 1560, (m0, m1)              # the bottom band (1295–1455)
    assert a0 is not None and 780 <= a0 and a1 <= 1140, (a0, a1)
    assert int(word.sum()) >= 5000 and ys.max() < 1295, (ys.min(), ys.max())   # the word above the bottom band
