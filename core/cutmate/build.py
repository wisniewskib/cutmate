"""plan.json + A-roll + theme pack → HyperFrames project (out/composition/).

Root index.html: A-roll inside #split > #cam > #shake, one sub-composition host per graphic, #flash, #captions,
SFX <audio> tags, and web/cutmate.js driving captions / punch-ins / hits / split moves on the main timeline.
9:16 with a plan `panel`: one persistent panel frame host, its items swapping inside it, full-frame scenes, the A-roll
moved once so the face sits in the bottom part and the captions on the seam (`panel_offsets`).
"""
import html as _html
import json
import os
import re
import shutil
import statistics
import unicodedata
from dataclasses import replace
from pathlib import Path

from .captions import to_srt
from .chapters import chapters_txt
from .config import CAPTION_MODES, DEFAULT_CAPTIONS
from .cut import load_timed
from .effects import (THREE_MARK, VENDOR_URL, effect_meta, find_effect, held_slice, libs_head, lint_effect, tip_slice, track_slice,
                      vendor_files, vendor_root)
from .errors import CutmateError, PlanError
from .formats import format_of, size_of
from .hf import ensure_project, hf
from .layout import CLASSIC, SPLIT_DEFAULTS, theme_layout
from .media import duration, run
from .music import carve, pick_source, prepare_music
from .paths import assets_dir, plugin_root, theme_dir, web_dir
from .plan import PLATE, SCENE_FADE, Graphic, _expanded_pair, load_plan, panel_box, panel_summary, plate_chapters
from .tracks import FINGERS, TIP_TRACKS, pick_hand

CHAPTER_LABEL = {"pl": "ROZDZIAŁ", "en": "CHAPTER"}
GLITCH_AMP = 0.022            # the A-roll glitch's peak R / B split, as a share of the frame width
LEAD = 0.3                    # host starts this much before the graphic's word (entrance lead-in)
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
ILLUSTRATIVE = {"pl": "ILUSTRACYJNIE", "en": "ILLUSTRATIVE"}
_SECTION = re.compile(r"<(style|markup|script)>(.*?)</\1>", re.S)
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")

SUBCOMP = """<!doctype html>
<html lang="{lang}"><head><meta charset="UTF-8" /></head><body><template>
  <link rel="stylesheet" href="assets/tokens.css" />
  <link rel="stylesheet" href="assets/theme.css" />
  <style>#{cid} {{ position: absolute; inset: 0; pointer-events: none; }}
{style}</style>
  <div id="{cid}" data-composition-id="{cid}" data-width="{w}" data-height="{h}" data-duration="{dur}">{markup}</div>
  <script>(function () {{
    const tl = gsap.timeline({{ paused: true }});
    const root = {root};
    const P = {params};
    const U = {u_open}{{
      el(tag, cls, text, parent) {{ const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; (parent || root).appendChild(e); return e; }},
      counter(el, fmt) {{ const d = {{}}; let v = 0; Object.defineProperty(d, "v", {{ get: () => v, set: (n) => {{ v = n; el.textContent = fmt(n); }} }}); return d; }},
      out(target, t) {{ tl.to(target, {{ opacity: 0, y: -30, duration: 0.2, ease: "power2.in", immediateRender: false }}, Math.max(0, t)); }},
      seed(n) {{ let a = (n >>> 0) || 1; return () => {{ a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }}; }},
    }}{u_close};
{script}{fade}
    window.__timelines["{cid}"] = tl;
  }})();</script>
</template></body></html>
"""
FX_OPEN = 'Object.assign(window.CutmateFX.make(tl, root, "{cid}", P), '
REGION = '<div class="cm-region" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;overflow:hidden">{markup}</div>'
FADE = ("\n    tl.set(root, {{ autoAlpha: 0 }}, 0); tl.to(root, {{ autoAlpha: 1, duration: {f} }}, P.at); "
        "tl.to(root, {{ autoAlpha: 0, duration: {f}, immediateRender: false }}, Math.max(P.at + {f}, P.end - {f}));")
SLIDE_IN = '\n    tl.fromTo(root, {{ y: -{d} }}, {{ y: 0, duration: 0.45, ease: "power3.out" }}, P.at); '   # = split.html's panel
SLIDE_OUT = 'tl.to(root, {{ y: -{d}, duration: 0.4, ease: "power3.inOut", immediateRender: false }}, Math.max(P.at + 0.45, P.end - 0.4));'
SLIDE = SLIDE_IN + SLIDE_OUT
FADE_IN = "\n    tl.fromTo(root, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.2 }, P.at);"
HANDOFF = 0.2                 # a panel item's host runs on this long after the next item starts (the next one covers it)
BAND_FADE = 0.15              # a panel item fades out / in under a band graphic (title, counter…) that overlaps it


def _panel_moves(params: dict, d: int) -> str:
    """A panel item's own moves: the first one slides in with the panel, the last one out with it, the rest swap in place
    (cut: nothing, fade: 0.2 s) and are covered by the next item."""
    enter = {"slide": SLIDE_IN.format(d=d).rstrip(), "fade": FADE_IN}.get(params.get("_enter"), "")
    exit_ = "\n    " + SLIDE_OUT.format(d=d) if params.get("_exit") == "slide" else ""
    return enter + exit_


def hide_spans(spans: list[tuple]) -> list[list]:
    """Merge one host's hidden spans (a, fade-out, b | None, fade-in) — overlapping ones become one."""
    out = []
    for a, da, b, db in sorted(spans, key=lambda x: x[0]):
        if out and (out[-1][2] is None or a <= out[-1][2]):
            last = out[-1]
            if last[2] is not None and (b is None or b > last[2]):
                last[2], last[3] = b, db
            continue
        out.append([a, da, b, db])
    return [[round(a, 3), da, None if b is None else round(b, 3), db] for a, da, b, db in out]

INDEX = """<!doctype html>
<html lang="{lang}" class="{fcls}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={w}, height={h}" />
    <title>cutmate</title>
    <script src="assets/vendor/gsap@3.14.2/dist/gsap.min.js"></script>{fx_head}
    <link rel="stylesheet" href="assets/tokens.css" />
    <link rel="stylesheet" href="assets/theme.css" />
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{end}" data-width="{w}" data-height="{h}">
      <div id="split"><div id="cam"><div id="shake"><video id="aroll" src="assets/aroll.mp4" data-start="0" data-duration="{vdur}" data-media-start="0" data-track-index="0" playsinline data-has-audio="true"></video></div></div></div>{fx_svg}
{hosts}
      <div id="flash"></div>
      <div id="captions" class="clip" data-start="0" data-duration="{end}" data-track-index="5"></div>
{audio}
    </div>
    <script src="assets/cutmate.js"></script>
    <script>
      const CFG = {cfg};
      const tl = gsap.timeline({{ paused: true }});
      Cutmate.build(tl, CFG);
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""


# the A-roll glitch filters (cfg.glitch, cutmate.js glitch()): #cm-rgb splits R / G / B (the R and B feOffset dx are
# stepped from ±18 px to 0), #cm-wave displaces the frame by a seeded turbulence (scale 60 -> 0). Only with a glitch
FX_SVG = """
      <svg id="cm-fx" width="0" height="0" aria-hidden="true" style="position:absolute;width:0;height:0;overflow:hidden">
        <filter id="cm-rgb" x="-2%" y="0" width="104%" height="100%" color-interpolation-filters="sRGB">
          <feColorMatrix in="SourceGraphic" type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="r" />
          <feOffset class="cm-r" in="r" dx="0" dy="0" result="ro" />
          <feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="g" />
          <feColorMatrix in="SourceGraphic" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" result="b" />
          <feOffset class="cm-b" in="b" dx="0" dy="0" result="bo" />
          <feBlend in="ro" in2="g" mode="screen" result="rg" />
          <feBlend in="rg" in2="bo" mode="screen" />
        </filter>
        <filter id="cm-wave" x="-5%" y="-5%" width="110%" height="110%" color-interpolation-filters="sRGB">
          <feTurbulence type="fractalNoise" seed="7" baseFrequency="0.004 0.03" numOctaves="2" result="n" />
          <feDisplacementMap in="SourceGraphic" in2="n" scale="0" xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </svg>"""


def _fx_head(effect_texts: list[str]) -> str:
    """effects.js + the libraries the project's custom effects use; nothing at all without custom effects."""
    if not effect_texts:
        return ""
    libs = libs_head(effect_texts)
    return '\n    <script src="assets/effects.js"></script>' + (f"\n    {libs}" if libs else "")


def _js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def _core(word: str) -> str:
    return re.sub(r"[^\w%']", "", str(word).replace("\u2019", "'").upper())


def _is_key(core: str, keys: set) -> bool:
    """A word is key when its core equals a key, or starts with a key (>= 4 chars) plus an apostrophe / <= 3 letters."""
    if core in keys:
        return True
    for k in keys:
        if len(k) >= 4 and core.startswith(k):
            rest = core[len(k):]
            if rest.startswith("'") or (len(rest) <= 3 and rest.isalpha()):
                return True
    return False


def caption_pages(words: list[dict], end: float, key: list[str], max_words: int = 3, max_chars: int = 16,
                  pause: float = 0.35) -> list[dict]:
    pages, cur, n = [], [], 0
    for w in (x for x in words if str(x["word"]).strip()):
        if cur:
            prev = cur[-1]
            if (len(cur) >= max_words or n + len(w["word"]) > max_chars or prev["seg"] != w["seg"]
                    or prev["word"][-1:] in ",.?!…:;" or w["start"] - prev["end"] > pause):
                pages.append(cur)
                cur, n = [], 0
        cur.append(w)
        n += len(w["word"]) + 1
    if cur:
        pages.append(cur)
    keys = {_core(k) for k in key}
    out = []
    for i, p in enumerate(pages):
        start = max(0.0, p[0]["start"] - 0.04)
        nxt = pages[i + 1][0]["start"] - 0.04 if i + 1 < len(pages) else end
        stop = min(nxt, max(p[-1]["end"] + 0.8, start + 0.2), end - 0.01)
        ws = []
        for w in p:
            c = _core(w["word"])
            cls = "key" if _is_key(c, keys) else "num" if re.search(r"\d", w["word"]) else ""
            ws.append([w["word"], round(max(0.0, w["start"] - 0.04), 3), cls])
        out.append({"start": round(start, 3), "end": round(stop, 3), "words": ws})
    return out


FACE_DEFAULT = [0.5, 0.4]


def cam_from_cuts(timed: list[dict], fmt: str = "9:16", face: dict | None = None,
                  bgs: list | tuple = ()) -> list[list[float]]:
    """Punch-in on every other cut. 16:9 zooms further and centres on the speaker's face.

    While a bg is on screen the camera is unzoomed (scale 1.0): the cut-out is the unzoomed A-roll."""
    if fmt != "16:9":
        cam = [[round(float(s["start"]), 3), 1.0 if i % 2 == 0 else 1.12] for i, s in enumerate(timed)]
    else:
        face = face or {}
        cam = []
        for i, s in enumerate(timed):
            fx, fy = face.get(str(s["id"]), FACE_DEFAULT)
            cam.append([round(float(s["start"]), 3), 1.0 if i % 2 == 0 else 1.25, round(fx, 3), round(fy, 3)])
    if not bgs:
        return cam

    def under_bg(t):
        return any(a - 1e-9 <= t < b - 1e-9 for a, b in bgs)

    def entry_at(t):
        return next((c for c in reversed(cam) if c[0] <= t + 1e-9), cam[0])
    out = {c[0]: [c[0], 1.0, *c[2:]] if under_bg(c[0]) else list(c) for c in cam}
    for a, b in bgs:
        a, b = round(float(a), 3), round(float(b), 3)
        out[a] = [a, 1.0, *entry_at(a)[2:]]
        e = entry_at(b)
        out[b] = [b, 1.0 if under_bg(b) else e[1], *e[2:]]
    return [out[t] for t in sorted(out)]


CAM_ORIGIN = (0.5, 0.46)      # theme.css: #cam { transform-origin: 50% 46%; } (9:16 cam entries carry no origin)
SPLIT_DY = 300                # #split moves the A-roll this far down while a split panel is on screen (cutmate.js)
FACE_Y = 0.40                 # where the face sits in the A-roll frame (fraction of H) when plan.face has nothing
FACE_IN_HALF = 0.5            # the persistent panel puts the face this far down the bottom part (0.5: dy 672 at 0.5 / 0.40)
CAPTION_MID = 1375            # theme.css: #captions top 1250 + height 250 / 2 (9:16)
CAPTION_TEXT = {"9:16": (CAPTION_MID, 80), "16:9": (940, 60)}   # burned caption text: centre y, half height (theme.css)
PALM_LIFT = 0.05   # a palm-placed effect sits this far (frame fraction) above the palm centre, not on the fingers
SAFE = {(1080, 1920): [60, 192, 960, 1344], (1920, 1080): [60, 60, 1800, 800]}  # x, y, w, h a placed chip stays in


def caption_band(fmt: str, mode: str, t: float, panel: dict | None = None, cap_dy: int = 0,
                 drops: list | tuple = ()) -> list[int] | None:
    """Where the burned captions are at time t, [y0, y1] in frame px: the caption text band of theme.css (9:16 bottom,
    centred on CAPTION_MID; 16:9 lower third), moved onto the seam by cap_dy while the persistent panel is up — except
    under a full-frame WOW scene (`drops`: its [start, end]), where they stay in the bottom band. None when nothing is
    burned in (srt / none)."""
    if mode not in ("burn", "both") or fmt not in CAPTION_TEXT:
        return None
    mid, half = CAPTION_TEXT[fmt]
    if panel and panel["start"] - 1e-9 <= t <= panel["end"] + 1e-9 and \
            not any(a - 1e-9 <= t <= b + 1e-9 for a, b in drops):
        mid += cap_dy
    return [mid - half, mid + half]


PANEL_IN, PANEL_OUT = (0.45, "power3.out"), (0.4, "power3.inOut")   # cutmate.js splits(): the panel row's moves
DROP_EASE = "power2.inOut"


def caption_moves(pn: dict, cap_dy: int, t_out: float | None, drops: list | tuple,
                  fade: float = SCENE_FADE) -> tuple[int, list[list]]:
    """#captions y over a split-panel video with full-frame WOW scenes (cfg.cap_moves; the panel row then leaves
    #captions alone): (y at 0, [[t, from, to, dur, ease], …]). On the seam (cap_dy) while the panel is up, at the bottom
    (0) otherwise and under every drop [a, b] — down over the scene's fade in from a, back over its fade out ending at b.
    One tween at a time: a move that starts while the previous one runs waits for it, so each starts where the last
    one left off (never two tweens on the same y)."""
    events = [] if pn["open_at_zero"] else [(pn["start"], "up", 1, *PANEL_IN)]
    if t_out is not None:
        events.append((t_out, "up", -1, *PANEL_OUT))
    for a, b in drops:
        events += [(a, "drop", 1, fade, DROP_EASE), (max(a, b - fade), "drop", -1, fade, DROP_EASE)]
    state = {"up": 1 if pn["open_at_zero"] else 0, "drop": 0}
    for t, k, d, *_ in events:                         # a drop already on at 0 counts from the start
        if k == "drop" and d > 0 and t <= 1e-9:
            state["drop"] += 1
    events = [e for e in events if not (e[1] == "drop" and e[2] > 0 and e[0] <= 1e-9)]

    def target():
        return cap_dy if state["up"] > 0 and state["drop"] <= 0 else 0
    y0 = cur = target()
    moves, busy = [], 0.0
    for t in sorted({round(e[0], 3) for e in events}):
        group = [e for e in events if round(e[0], 3) == t]
        for _, k, d, *_ in group:
            state[k] += d
        new = target()
        if new != cur:
            dur, ease = max((e[3], e[4]) for e in group)
            start = round(max(t, busy), 3)
            moves.append([start, cur, new, dur, ease])
            busy, cur = start + dur, new
    return y0, moves


def panel_offsets(ratio: float, face_y: float, H: int = 1920) -> tuple[int, int]:
    """(dy, capDy) while the persistent panel is up: #split moves down by dy so the face lands in the bottom part,
    the caption box centre moves onto the seam (y = ratio × H)."""
    dy = round(H * (ratio + (1 - ratio) * FACE_IN_HALF) - face_y * H)
    return min(max(dy, 0), round(ratio * H)), round(ratio * H) - CAPTION_MID


def screen_point(x: float, y: float, t: float, cam: list, splits: list, sides: list, W: int, H: int) -> tuple:
    """Where a tracked point (fractions of the A-roll frame at A-roll time t) is on screen, in px: through the active
    camera entry (16:9 [t, s, ox, oy] about the face, 9:16 [t, s] about #cam's origin), the settled split / side
    offsets of #split (from the move in until the move out ends), then clamped into the frame."""
    s, ox, oy = 1.0, *CAM_ORIGIN
    for c in cam:
        if c[0] <= t + 1e-9:
            s = c[1]
            if len(c) >= 4:
                ox, oy = c[2], c[3]
    px = (ox + (x - ox) * s) * W
    py = (oy + (y - oy) * s) * H
    for e in splits:                                     # [tIn, tOut] (a split: SPLIT_DY) or [tIn, tOut|None, dy, …]
        b = float("inf") if e[1] is None else e[1]
        if e[0] - 1e-9 <= t <= b + 0.4 + 1e-9:
            py += e[2] if len(e) >= 3 else SPLIT_DY
            break
    for a, b, dx in sides:
        if a - 1e-9 <= t <= b + 0.4 + 1e-9:
            px += dx
    return round(min(W, max(0.0, px)), 1), round(min(H, max(0.0, py)), 1)


def _scale_at(cam: list[list[float]], t: float) -> float:
    s = 1.0
    for c in cam:
        if c[0] <= t + 1e-9:
            s = c[1]
    return s


SOFT_FLASH = 0.35   # the #flash peak of a hit on a bg effect that draws the cut-out (its own reveal; 0.8 would white it out)


def hits_for(graphics: list[Graphic], cam: list[list[float]], timed: list[dict], end: float,
             soft: set | frozenset = frozenset()) -> list[list[float]]:
    """[t, scale, punch] per hit; a graphic in `soft` (by id) gets a 4th entry, its #flash peak (SOFT_FLASH)."""
    bgs = [(g.start, g.end) for g in graphics if g.type == "bg"]
    cuts = sorted([float(s["start"]) for s in timed] + [t for r in bgs for t in r])  # camera changes end a punch
    out = []
    for g in graphics:
        if not g.hit:
            continue
        t = g.params.get("_hit_at", g.start)            # "hit": "<anchor>" shakes at that word
        nxt = next((c for c in cuts if c > t + 1e-9), end)
        punch = min(0.5, nxt - (t + 0.12) - 0.02)
        if any(a - 1e-9 <= t < b for a, b in bgs):
            punch = 0                                    # no punch-in over a bg cut-out (shake only)
        out.append([t, _scale_at(cam, t), round(punch, 3) if punch >= 0.15 else 0] + ([SOFT_FLASH] if id(g) in soft else []))
    return out


def _theme_meta(th: Path) -> dict:
    f = th / "theme.json"
    try:
        meta = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CutmateError(f"{f}: cannot read theme ({e})") from None
    if not isinstance(meta, dict) or not isinstance(meta.get("sfx"), dict) or not (
            isinstance(meta.get("hit_sfx"), list) and len(meta["hit_sfx"]) == 2):
        raise CutmateError(f"{f}: theme.json needs an \"sfx\" object and a \"hit_sfx\" [name, volume] pair")
    return meta


def _prune(folder: Path, keep: set) -> None:
    for f in folder.iterdir():
        if f.is_file() and f.name not in keep:
            f.unlink()


FALLBACK = ("bg", "side", "chapter", "pip", "lower-third", "panel", "panel-media", "scene")  # newer than many user themes


def _component(th: Path, kind: str, theme: str, warned: set) -> Path:
    """The theme's component file; for newer types a theme lacks, the bundled clean one (with a WARN, once per type)."""
    p = th / "components" / f"{kind}.html"
    if p.exists() or kind not in FALLBACK:
        return p
    if kind not in warned:
        warned.add(kind)
        print(f"WARN theme {theme} has no {kind} component — using clean's")
    return plugin_root() / "themes" / "clean" / "components" / f"{kind}.html"


def _sections(path: Path) -> dict:
    if not path.exists():
        raise CutmateError(f"theme has no {path.name} component — update the theme or run theme-check")
    d = dict(_SECTION.findall(path.read_text(encoding="utf-8")))
    if "script" not in d:
        raise CutmateError(f"{path}: component has no <script> section")
    return d


def _ascii_name(path: Path, n: int) -> str:
    stem = unicodedata.normalize("NFKD", path.stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()[:40] or "media"
    return f"m{n:02d}-{stem}{path.suffix.lower()}"


def _copy_media(src: str, assets: Path, media_map: dict) -> str:
    if src not in media_map:
        name = _ascii_name(Path(src), len(media_map) + 1)
        _copy_if_newer(Path(src), assets / "media" / name)
        media_map[src] = f"assets/media/{name}"
    return media_map[src]


def _copy_if_newer(src: Path, dst: Path) -> None:
    if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime or src.stat().st_size != dst.stat().st_size:
        shutil.copy2(src, dst)


def _sync_dir(src: Path, dst: Path) -> None:
    """Mirror src into dst: copy new / changed files, remove what src no longer has."""
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.rglob("*"):
        if f.is_file():
            t = dst / f.relative_to(src)
            t.parent.mkdir(parents=True, exist_ok=True)
            _copy_if_newer(f, t)
    for f in sorted(dst.rglob("*"), reverse=True):     # children before their folders
        if not (src / f.relative_to(dst)).exists():
            shutil.rmtree(f) if f.is_dir() else f.unlink()


FACE_PX = 360


def face_clip(aroll: Path, start: float, end: float, center: list[float], size: tuple[int, int], dst: Path) -> Path:
    """The pip circle: a muted square crop around the face, cut from the A-roll for [start, end]."""
    W, H = size
    side = round(H * 0.6) // 2 * 2
    cx = min(max(center[0] * W, side / 2), W - side / 2)
    cy = min(max(center[1] * H, side / 2), H - side / 2)
    dst = Path(dst)
    tmp = dst.with_name(dst.stem + ".tmp.mp4")
    r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", aroll,
             "-vf", f"crop={side}:{side}:{int(cx - side / 2)}:{int(cy - side / 2)},scale={FACE_PX}:{FACE_PX}",
             "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", "30", "-pix_fmt", "yuv420p", tmp])
    if r.returncode or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise CutmateError(f"cannot cut the pip face clip: {' '.join(r.stderr.split())[-300:]}")
    os.replace(tmp, dst)
    return dst


def bg_cutout(aroll: Path, start: float, end: float, media_dir: Path) -> str:
    """Speaker without background for [start, end] (transparent WebM), cached per range and A-roll."""
    stem = f"bgcut-{int(start * 1000)}-{int(end * 1000)}"
    final = media_dir / f"{stem}.webm"
    if final.exists() and final.stat().st_mtime >= Path(aroll).stat().st_mtime:
        return final.name
    src, tmp = media_dir / f"bgsrc-{stem[6:]}.mp4", media_dir / f"{stem}.tmp.webm"
    try:
        r = run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
                 "-i", aroll, "-an", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", src])
        if r.returncode:
            raise CutmateError(f"cannot cut the bg source: {' '.join(r.stderr.split())[-300:]}")
        r = run(hf("remove-background", src.name, "-o", tmp.name, "--device", "auto"), cwd=media_dir)
        if r.returncode or not tmp.exists():
            raise CutmateError(f"background removal failed: {' '.join((r.stdout + r.stderr).split())[-300:]}")
        os.replace(tmp, final)
        return final.name
    finally:
        src.unlink(missing_ok=True)
        tmp.unlink(missing_ok=True)


def _seg_at(timed: list[dict], t: float) -> str:
    return next((str(s["id"]) for s in timed if s["start"] <= t + 1e-9 < s["end"]), str(timed[-1]["id"]))


def _media_tag(cid: str, g: Graphic, P: dict) -> str:
    if Path(g.params["media"]).suffix.lower() in VIDEO_EXTS:
        vdur = round(min(P["end"] - P["at"], duration(Path(g.params["media"]))), 3)
        P["kind"] = "video"
        return (f'<video id="{cid}-v" class="clip" data-hf-media-start-basis="local" data-start="{P["at"]}" '
                f'data-duration="{vdur}" src="{P["media"]}" muted playsinline></video>')
    P["kind"] = "image"
    return f'<div class="img" style="background-image:url(\'{P["media"]}\')"></div>'


def _hand_params(tr: dict, g: Graphic, host_start: float, size: tuple, origin: tuple, screen, face_half: int = 0) -> dict:
    """For an effect whose index.json has "tips": per hand side with any sample in [start - 0.75, end], in region px and
    local s: P.tips[side] = 5 fingertip series [[t, x, y, ext], …] (thumb … pinky, tip_slice), P.palm_open[side] =
    [[t, 0|1], …] (the palm's open flag, off when the hand is gone), P.palms[side] = the palm centre (held_slice);
    P.faces = the face track (held_slice; the card keeps off it); P.lift = how far above the palm a palm-placed thing
    sits (px), P.safe = the SAFE box in region px — below the panel seam (face_half px) while a split panel is up, so
    the card stays in the speaker's half."""
    (W, H), (rx, ry) = size, origin
    tips, opened, palms = {}, {}, {}
    for side in ("left", "right"):
        names = [f"{f}_{side}" for f in FINGERS] + [f"palm_{side}"]
        if not any(g.start - 0.75 <= s[0] <= g.end for n in names for s in tr.get(n, [])):
            continue
        tips[side] = [[[t, round(x - rx, 1), round(y - ry, 1), e]
                       for t, x, y, e in tip_slice(tr.get(f"{f}_{side}", []), g.start, g.end, host_start, W, H, screen)]
                      for f in FINGERS]
        palm = tr.get(f"palm_{side}", [])
        opened[side] = [[t, int(e)] for t, _, _, e in tip_slice(palm, g.start, g.end, host_start, W, H, screen)]
        palms[side] = [[t, round(x - rx, 1), round(y - ry, 1)]
                       for t, x, y in held_slice(palm, g.start, g.end, host_start, W, H, screen)]
    faces = [[t, round(x - rx, 1), round(y - ry, 1)]
             for t, x, y in held_slice(tr.get("face", []), g.start, g.end, host_start, W, H, screen)]
    sx, sy, sw, sh = SAFE.get((W, H), [0, 0, W, H])
    if face_half > sy:
        sy, sh = face_half, max(0, sy + sh - face_half)
    return {"tips": tips, "palm_open": opened, "palms": palms, "faces": faces, "lift": round(PALM_LIFT * H, 1),
            "safe": [sx - rx, sy - ry, sw, sh]}


def subcomp(cid: str, g: Graphic, host_start: float, theme: Path, assets: Path, media_map: dict, lang: str,
            size: tuple = (1080, 1920), extra_tags: dict | None = None, comp_path: Path | None = None,
            tracks: dict | None = None, assets_url: str | None = None, screen=None, caption_band: list | None = None,
            face: list | None = None, tips: bool = False, face_half: int = 0) -> str:
    sec = _sections(comp_path or theme / "components" / f"{g.type}.html")
    W, H = size
    screen = screen or (lambda x, y, t: (round(x * W, 1), round(y * H, 1)))  # noqa: E731  tracked point -> screen px
    loc = lambda t: round(max(0.0, t - host_start), 3)  # noqa: E731
    P = {k: v for k, v in g.params.items() if k != "_hit_at"}
    P.update(at=loc(g.start), end=loc(g.end), lang=lang)
    if g.type == "list":
        P["items"] = [{"text": it["text"], "at": loc(it["at"])} for it in g.params["items"]]
    if g.type == "bars":
        P["note"] = ILLUSTRATIVE.get(lang, ILLUSTRATIVE["en"]) if g.params.get("illustrative") else ""
    for k in ("media", "image", "logo", "icon"):
        if k in P:
            P[k] = _copy_media(g.params[k], assets, media_map)
    if g.type == "chip":
        P.pop("place", None)
        xy = P.pop("place_xy", None)
        lift = PALM_LIFT if P.pop("place_track", None) else 0.0
        if xy:                                           # place: gesture -> centre on the pointed spot, in frame px
            P["place"] = list(screen(xy[0], xy[1] - lift, g.start))
            P["safe"] = SAFE.get((W, H), [0, 0, W, H])
    root, u_open, u_close, fade = f'document.getElementById("{cid}")', "", "", ""
    region = None
    if g.type == "custom":
        region = g.params.get("region")
        rx, ry, rw, rh = region or [0, 0, W, H]
        follow = g.params.get("follow")
        track = []
        if follow and tracks:
            tn = pick_hand(tracks["tracks"], g.start, g.end) if follow == "hand" else follow
            track = [[t, round(x - rx, 1), round(y - ry, 1)]
                     for t, x, y in track_slice(tracks["tracks"].get(tn, []), g.start, g.end, host_start, W, H, screen)]
        P = dict(g.params.get("params") or {})          # user params first: timing / size keys always win
        m = P.get("media")
        if isinstance(m, str) and Path(m).is_absolute() and Path(m).exists():
            P["media"] = _copy_media(m, assets, media_map)   # params.media (resolved by the plan) -> asset URL
        P.update(name=g.params["name"], at=loc(g.start), end=loc(g.end), lang=lang, w=rw, h=rh,
                 dur=round(g.end - host_start, 3), track=track, vendor=VENDOR_URL)
        P.pop("panel", None)                             # build-owned: a panel item's explainer builds in at once
        if g.params.get("_panel"):
            P["panel"] = True
        if follow:
            P["follow"] = follow                         # meant to follow: no samples → the effect stays hidden
        if assets_url:
            P["assets"] = assets_url
        if "_hit_at" in g.params:                        # "hit": "<anchor>": the impact time (local s)
            P["hit_at"] = loc(g.params["_hit_at"])
        if face:                                         # the bg segment's face (plan.face) in region px
            P["face"] = [round(face[0] * W - rx, 1), round(face[1] * H - ry, 1)]
            faces = [[t, round(x - rx, 1), round(y - ry, 1)] for t, x, y in held_slice(
                (tracks or {}).get("tracks", {}).get("face", []), g.start, g.end, host_start, W, H, screen)]
            if faces:                                    # the tracked face over time (a held object keeps off it)
                P["faces"] = faces
        if caption_band:                                 # the burned captions in region px (only where they cross it)
            y0, y1 = max(0, caption_band[0] - ry), min(rh, caption_band[1] - ry)
            if y1 > y0:
                P["caption_band"] = [round(y0), round(y1)]
        if g.params.get("place_xy"):
            px, py = screen(g.params["place_xy"][0], g.params["place_xy"][1], g.start)
            P["place"] = [round(px - rx, 1), round(py - ry, 1)]
        if g.params.get("place_track") and tracks:       # open palm: sit just above it and follow it, held through gaps
            lifted = lambda x, y, t: screen(x, y - PALM_LIFT, t)  # noqa: E731
            held = lambda name: [[t, round(x - rx, 1), round(y - ry, 1)] for t, x, y in held_slice(  # noqa: E731
                tracks["tracks"].get(name, []), g.start, g.end, host_start, W, H, lifted)]
            hands = {}
            for side in ("left", "right"):
                samples = tracks["tracks"].get(f"palm_{side}", [])
                if any(g.start - 0.75 <= s[0] <= g.end for s in samples):
                    hands[side] = held(f"palm_{side}")
            if hands:
                P["hands"] = hands                       # both palms (effects that use two hands)
            mine = held(g.params["place_track"])
            if mine and not follow:
                P["track"] = mine
                P["place"] = list(mine[0][1:])
        if tips and tracks:                              # meta "tips" (hand-control): fingertips, palms, open palm
            P.update(_hand_params(tracks["tracks"], g, host_start, (W, H), (rx, ry), screen, face_half))
        if "media" in g.params:
            P["media"] = _copy_media(g.params["media"], assets, media_map)
        u_open, u_close = FX_OPEN.format(cid=cid), ")"
        if region:
            root = f'document.querySelector("#{cid} > .cm-region")'
        if g.params.get("_panel"):
            fade = _panel_moves(g.params, ry * 2 + rh)
        elif g.params.get("_fade"):
            fade = FADE.format(f=g.params["_fade"])
        elif g.params.get("_slide"):
            fade = SLIDE.format(d=g.params["_slide"])
    media_tag = ""
    if g.type in ("split", "pip"):
        P["fit"] = g.params.get("fit", "contain")
        if "media" in g.params:                          # a split with an effect has an empty media box
            media_tag = _media_tag(cid, g, P)
    if g.type == "side":
        P["side"] = "l" if g.params["speaker"] == "right" else "r"
        P["fit"] = g.params.get("fit", "cover")
        if "media" in g.params:
            media_tag = _media_tag(cid, g, P)
        else:
            P["side"] += " side-fx"
    if g.type == "panel":
        P["panel_h"] = round(g.params["ratio"] * H)
    if g.type == "panel-media":
        ratio = g.params.get("ratio", SPLIT_DEFAULTS.ratio)
        P["fit"] = g.params.get("fit", "cover")
        P["box_h"] = panel_box(ratio)[3]
        media_tag = _media_tag(cid, g, P)
        fade = _panel_moves(g.params, round(ratio * H))
    if g.type == "scene":
        P["fade"] = SCENE_FADE                           # scene.html fades in / out by it (one constant: plan.SCENE_FADE)
        media_tag = _media_tag(cid, g, P)
    back_tag = _media_tag(cid, g, P) if g.type == "bg" and "media" in g.params else ""
    tags = {"media_tag": media_tag, "back_tag": back_tag, **(extra_tags or {})}
    markup = _PLACEHOLDER.sub(lambda m: tags[m.group(1)] if m.group(1) in tags
                              else _html.escape(str(P.get(m.group(1), ""))), sec.get("markup", ""))
    if region:
        markup = REGION.format(x=region[0], y=region[1], w=region[2], h=region[3], markup=markup)
    script = sec["script"]
    if g.type == "custom" and re.search(THREE_MARK, script):
        # hyperframes lint checks each composition for a Three.js import; ours comes from the importmap in index.html
        script = '// import("three") is resolved by the importmap in index.html (U.three)\n' + script
    style = sec.get("style", "")
    if W > H:                                            # hyperframes scopes every selector under the composition, so an
        style = style.replace("html.f169 ROOT", "ROOT")  # `html.f169` ancestor never matches: 16:9 rules apply by build
    style = style.replace("ROOT", f"#{cid} > .cm-region" if region else f"#{cid}")
    return SUBCOMP.format(lang=lang, cid=cid, w=W, h=H, dur=round(g.end - host_start, 3), root=root, u_open=u_open,
                          u_close=u_close, fade=fade, style=style,
                          markup=markup, params=_js(P), script=script)


def _sfx_cues(g: Graphic, meta: dict) -> list[tuple]:
    if g.sfx is False:
        return []
    if isinstance(g.sfx, str):
        return [(g.sfx, g.start, 0.35)]
    kind = "chapter" if g.params.get("_chapter") else g.type    # a chapter_fx plate keeps the chapter sound
    cues = [(n, g.start + off, vol) for n, off, vol in meta["sfx"].get(kind, [])]
    if g.type == "list":
        cues += [(n, it["at"] + off, vol) for it in g.params["items"] for n, off, vol in meta["sfx"].get("list.item", [])]
    return cues


def sfx_tags(cues: list[tuple], end: float, assets: Path) -> list[str]:
    manifest = json.loads((assets_dir() / "sfx" / "manifest.json").read_text(encoding="utf-8"))
    tags, seen, lanes = [], set(), []
    for name, t, vol in sorted(cues, key=lambda c: c[1]):
        if name not in manifest:
            raise CutmateError(f"unknown sound {name!r} (available: {', '.join(sorted(manifest))})")
        t = max(0.0, t)
        key = (name, round(t, 2))
        if key in seen or t >= end - 0.05:
            continue
        seen.add(key)
        entry = manifest[name]
        shutil.copy2(assets_dir() / "sfx" / entry["file"], assets / "sfx" / entry["file"])
        d = round(min(entry["duration"], end - t), 3)
        lane = next((i for i, busy in enumerate(lanes) if busy <= t), len(lanes))
        if lane == len(lanes):
            lanes.append(0.0)
        lanes[lane] = t + d
        tags.append(f'      <audio id="sfx-{len(tags) + 1}" src="assets/sfx/{entry["file"]}" data-start="{round(t, 3)}" '
                    f'data-duration="{d}" data-track-index="{10 + lane}" data-volume="{vol}" data-audio-group="sfx"></audio>')
    return tags


def chapter_plates(plan, end: float, lang: str) -> list[Graphic]:
    """Full-screen plates for chapters 2+ (chapter 1 is the start of the video): the theme's chapter.html, or with
    plan.json "chapter_fx" that custom effect over the same span (params title / kicker / num, marked `_chapter`: it
    never counts toward the WOW caps)."""
    word = CHAPTER_LABEL.get(lang, CHAPTER_LABEL["en"])
    fx = getattr(plan, "chapter_fx", None)
    out = []
    for c in plate_chapters(plan.chapters, end):
        s, e, label = c["start"], round(min(c["start"] + PLATE, end - 0.05), 3), f"{word} {c['num']:02d}"
        if fx:
            out.append(Graphic("custom", s, e, {"name": fx, "params": {"title": c["title"], "kicker": label, "num": c["num"]},
                                                "_chapter": True}, False, None, -1))
        else:
            out.append(Graphic("chapter", s, e, {"num": c["num"], "title": c["title"], "label": label}, False, None, -1))
    return out


def checkpoint(g: Graphic) -> float:
    """The time a graphic is fully on screen (a list: its last item in) — where theme-check snapshots it."""
    t = max(it["at"] for it in g.params["items"]) if g.type == "list" else g.start
    return round(min(t + 0.4, g.end - 0.05), 2)


def build(out_dir: Path, theme: str = "clean", language: str = "pl", factcheck: bool = False,
          music: dict | None = None, captions: dict | None = None) -> dict:
    out = Path(out_dir).resolve()
    tall = format_of(out) == "9:16"                    # the theme layout applies to 9:16 only (16:9 is classic)
    lay = theme_layout(theme_dir(theme)) if tall else CLASSIC
    plan = load_plan(out, factcheck, lay if tall else None)
    fmt = plan.format
    W, H = size_of(fmt)
    mode = (captions or {}).get(fmt) or DEFAULT_CAPTIONS[fmt]
    if mode not in CAPTION_MODES:
        raise CutmateError(f"unknown caption mode {mode!r} for {fmt} (use {', '.join(CAPTION_MODES)})")
    th = theme_dir(theme)
    meta = _theme_meta(th)
    if plan.chapter_fx:                                # the chapter plates' effect: found and linted before any file
        lint_effect(find_effect(plan.chapter_fx, out, theme))
    if not (out / "aroll.mp4").exists():
        raise CutmateError(f"{out / 'aroll.mp4'} not found — run `cutmate cut` first")
    proj = out / "composition"
    ensure_project(proj, fmt)
    A = proj / "assets"
    for d in (A / "fonts", A / "sfx", A / "media", A / "bgm", proj / "compositions"):
        d.mkdir(parents=True, exist_ok=True)
    _copy_if_newer(out / "aroll.mp4", A / "aroll.mp4")
    for f in ("tokens.css", "theme.css"):
        shutil.copy2(th / f, A / f)
    for f in (th / "fonts").glob("*.ttf"):
        shutil.copy2(f, A / "fonts" / f.name)
    shutil.copy2(web_dir() / "cutmate.js", A / "cutmate.js")

    words = json.loads((out / "work" / "aligned_words.json").read_text(encoding="utf-8"))
    timed = load_timed(out)
    end = plan.end
    media_map, hosts, cues, ids = {}, [], [], []
    items = sorted(plan.graphics + chapter_plates(plan, end, language), key=lambda g: g.start)
    keep_media = set()
    tr = plan.tracks
    effect_texts, warned, fx_used = [], set(), set()
    found = {}
    cam = cam_from_cuts(timed, fmt, plan.face, [(g.start, g.end) for g in plan.graphics if g.type == "bg"])
    splits = [[g.start, round(max(g.start + 0.45, g.end - 0.4), 3)] for g in plan.graphics if g.type == "split"]
    pn = plan.panel
    cap_dy = 0
    if pn:                                             # the persistent panel: the face moves into the bottom part once
        ys = [v[1] for v in plan.face.values()]
        dy, cap_dy = panel_offsets(pn["ratio"], statistics.median(ys) if ys else FACE_Y, H)
        if lay.captions == "bottom":
            cap_dy = 0
        pn_split = [pn["start"], None if pn["stays"] else round(max(pn["start"] + 0.45, pn["end"] - 0.4), 3),
                    dy, cap_dy, 1 if pn["open_at_zero"] else 0]
        splits.append(pn_split)
    panel_items = [g for g in items if g.params.get("_panel")]
    # the handoff only where an item runs up to the next one; an item with an earlier `until` ends there (a panel gap)
    item_end = {id(a): round(min(b.start + HANDOFF, end), 3) for a, b in zip(panel_items, panel_items[1:])
                if a.end >= b.start - 1e-3}
    scenes = [(g.start, g.end) for g in items if g.params.get("_scene")]
    hide = []
    panel_h = round(pn["ratio"] * H) if pn else 0

    def over_panel(x: Graphic) -> bool:
        """A band graphic that can cover the panel: not a hand-placed / following effect (it sits on the face half), not
        one whose region starts below the panel box."""
        if x.params.get("place_xy") or x.params.get("place_track") or x.params.get("follow"):
            return False
        if x.type == "custom" and effect_meta(find_effect(x.params["name"], out, theme)).get("tips"):
            return False                               # on the speaker's hand, in the face half
        r = x.params.get("region")
        return not (x.type == "custom" and r and r[1] >= panel_h)
    bands = [(x.start, x.end) for x in items if x.type != "panel" and not x.params.get("_panel")
             and not x.params.get("_scene") and over_panel(x)]
    sides = [[g.start, round(max(g.start + 0.45, g.end - 0.4), 3),
              round((1440 if g.params["speaker"] == "right" else 480) - plan.face.get(_seg_at(timed, g.start), FACE_DEFAULT)[0] * W)]
             for g in plan.graphics if g.type == "side"]

    def screen(x, y, t):
        return screen_point(x, y, t, cam, splits, sides, W, H)
    for g in items:                                    # resolve + lint every effect first: a failure writes nothing
        if g.type == "custom" and g.params["name"] not in found:
            found[g.params["name"]] = find_effect(g.params["name"], out, theme)
            lint_effect(found[g.params["name"]])
        if g.type == "custom" and effect_meta(found[g.params["name"]]).get("tips"):
            where = f'graphic #{g.index + 1} (custom {g.params["name"]})'
            if not tr:
                raise PlanError(f'{where}: needs hand tracks — run cutmate track "{out}"')
            if not all(n in tr["tracks"] for n in TIP_TRACKS):
                raise PlanError(f'{where}: needs fingertip tracks — run cutmate track --force "{out}"')
    # full-frame WOW scenes in a split-panel video: the captions drop from the seam to the bottom band meanwhile (media /
    # non-WOW scenes keep them on the seam); the panel row then leaves #captions to cfg.cap_moves
    drops = [(g.start, g.end) for g in items if g.params.get("_scene") and g.type == "custom"
             and effect_meta(found[g.params["name"]]).get("kind") == "wow"]
    pn_to = (end if pn["stays"] else pn["end"]) if pn else 0
    drops = [(a, b) for a, b in drops if pn and cap_dy and mode in ("burn", "both") and a < pn_to and b > pn["start"]]
    cap_moves = None
    if drops:
        cap_moves = list(caption_moves(pn, cap_dy, pn_split[1], drops))
        pn_split[3] = 0
    # bg pre-pass: each bg range is cut once; a bg effect whose markup has {{cut_tag}} draws the cut-out itself (so it
    # can put things behind the speaker) and its bg host gets none. A hit in such a pair shakes both hosts with #shake
    bg_of = {id(c): b for c in items for b in items if c.type == "custom" and b.type == "bg" and _expanded_pair(c, b)}
    cuts = {id(b): bg_cutout(A / "aroll.mp4", b.start, b.end, A / "media") for b in items if b.type == "bg"}
    cut_in_fx = {id(b) for c, b in ((c, bg_of[id(c)]) for c in items if id(c) in bg_of)
                 if "{{cut_tag}}" in _sections(found[c.params["name"]]).get("markup", "")}
    shake = {id(c) for c in items if id(c) in bg_of and id(bg_of[id(c)]) in cut_in_fx and bg_of[id(c)].hit}
    shake |= {id(b) for b in items if b.type == "bg" and id(b) in cut_in_fx and b.hit}
    # an effect whose index.json declares an impact ("impact": s after its start, "impact_tail": s it needs after it)
    # takes its hit there, so the shake, flash and hit sound land on its visual impact (P.hit_at): "hit": true at
    # start + impact, an anchor too close to the end pulled back to end - impact_tail
    for g in items:
        fx = g if g.type == "custom" else next((c for c in items if bg_of.get(id(c)) is g), None)
        if not g.hit or fx is None or fx.type != "custom":
            continue
        m = effect_meta(found[fx.params["name"]])
        if not isinstance(m.get("impact"), (int, float)) or isinstance(m.get("impact"), bool):
            continue
        t = g.params.get("_hit_at", g.start + float(m["impact"]))
        t = round(max(g.start, min(t, g.end - float(m.get("impact_tail") or 0))), 3)
        g.params["_hit_at"] = fx.params["_hit_at"] = t
    frame_hosts, scene_hosts, rest = [], [], 0
    for i, g in enumerate(items):
        cid = f"gx-{i + 1:02d}-{g.type}"
        ids.append(cid)
        hs = round(max(0.0, g.start - LEAD), 3)
        extra = None
        if g.params.get("_panel"):                     # an item swaps in place at its start (no lead-in); the host runs
            hs = g.start                               # on until the next item covers it (next start + 0.2 s), or to its `until`
            g = replace(g, end=item_end.get(id(g), g.end),
                        params={**g.params, "ratio": pn["ratio"]} if g.type == "panel-media" else g.params)
        if g.type == "pip":
            fx, fy = plan.face.get(_seg_at(timed, g.start), FACE_DEFAULT)
            name = f"pipface-{int(g.start * 1000)}-{int(g.end * 1000)}-{fx:.2f}-{fy:.2f}.mp4"
            dst = A / "media" / name
            if not dst.exists() or dst.stat().st_mtime < (A / "aroll.mp4").stat().st_mtime:
                face_clip(A / "aroll.mp4", g.start, g.end, [fx, fy], (W, H), dst)
            keep_media.add(name)
            loc_at = round(g.start - hs, 3)
            extra = {"face_tag": f'<video id="{cid}-f" class="clip" data-hf-media-start-basis="local" data-start="{loc_at}" '
                                 f'data-duration="{round(g.end - g.start, 3)}" src="assets/media/{name}" muted playsinline></video>'}
        cut_bg = g if g.type == "bg" else bg_of.get(id(g)) if id(bg_of.get(id(g))) in cut_in_fx else None
        if g.type == "bg" and id(g) in cut_in_fx:
            extra = {"cut_tag": ""}                    # drawn by its effect
        elif cut_bg is not None:
            name = cuts[id(cut_bg)]
            keep_media.add(name)
            loc_at = round(g.start - hs, 3)
            extra = {"cut_tag": f'<video id="{cid}-c" class="clip" data-hf-media-start-basis="local" data-start="{loc_at}" '
                                f'data-duration="{round(g.end - g.start, 3)}" src="assets/media/{name}" muted playsinline></video>'}
        assets_url = None
        face = None
        if g.type == "custom":
            comp_path = found[g.params["name"]]
            wow = effect_meta(comp_path).get("kind") == "wow"
            # WOW effects only (other effects keep their output byte-identical): where the burned captions are
            band = caption_band(fmt, mode, (g.start + g.end) / 2, pn, cap_dy, drops) if wow else None
            if wow and id(items[i]) in bg_of:            # a WOW bg effect: where the speaker's face is (P.face)
                face = plan.face.get(_seg_at(timed, g.start), FACE_DEFAULT)
            effect_texts.append(comp_path.read_text(encoding="utf-8"))
            folder = comp_path.parent / g.params["name"]     # the effect's own files (Lottie JSON, textures…)
            if folder.is_dir():
                _sync_dir(folder, A / "fx" / g.params["name"])
                fx_used.add(g.params["name"])
                assets_url = f"assets/fx/{g.params['name']}/"
        else:
            band = None
            comp_path = _component(th, g.type, theme, warned)
        (proj / "compositions" / f"{cid}.html").write_text(
            subcomp(cid, g, hs, th, A, media_map, language, size=(W, H), extra_tags=extra, comp_path=comp_path,
                    tracks=tr, assets_url=assets_url, screen=screen, caption_band=band, face=face,
                    tips=g.type == "custom" and bool(effect_meta(comp_path).get("tips")),
                    face_half=panel_h if pn and pn["start"] - 1e-6 <= g.start <= (end if pn["stays"] else pn["end"]) else 0),
            encoding="utf-8")
        scene = bool(g.params.get("_scene"))
        if g.type == "panel":
            track = 1                                  # under every graphic, over the A-roll
        elif scene:
            track = 4                                  # full-frame scenes: over the panel and graphics, under captions
        else:
            track, rest = 2 + rest % 2, rest + 1
        # Hosts covered by something opaque fade out on the main timeline (cutmate.js): a panel item under the next one
        # (from just before its start, over the handoff), any graphic under a full-frame scene (with the scene's fades).
        # Nothing changes on screen; `hyperframes check` sees a mid-fade mount, not text hidden under an opaque layer.
        spans = [(a, SCENE_FADE, b, SCENE_FADE) for a, b in scenes if not scene and a < g.end and b > hs]
        if items[i].params.get("_panel"):               # a band graphic over a panel item hides the item while it shows
            spans += [(max(a, hs), BAND_FADE, b, BAND_FADE) for a, b in bands if a < g.end and b > hs]
        if id(items[i]) in item_end:                   # (items[i]: the planned graphic, g: its host-length copy)
            spans.append((max(hs, g.end - HANDOFF - 0.02), HANDOFF + 0.02, None, 0))
        hide += [[f"#{cid}-slot", *h] for h in hide_spans(spans)]
        shake_cls = ' class="clip cm-shake"' if id(items[i]) in shake else ""
        (scene_hosts if scene else frame_hosts if g.type == "panel" else hosts).append(
            f'      <div id="{cid}-slot"{shake_cls} data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" '
            f'data-start="{hs}" data-duration="{round(g.end - hs, 3)}" data-track-index="{track}" '
            f'data-width="{W}" data-height="{H}"></div>')
        cues += _sfx_cues(g, meta)
    # stacking follows DOM order (data-track-index is display-only): the opaque panel frame first, right over the
    # A-roll and under every graphic whatever its start; full-frame scenes last, above the panel and its items
    hosts = frame_hosts + hosts + scene_hosts
    _prune(A / "media", {Path(v).name for v in media_map.values()} | keep_media)
    if (A / "fx").exists():
        for d in (A / "fx").iterdir():
            if d.name not in fx_used:
                shutil.rmtree(d) if d.is_dir() else d.unlink()
        if not fx_used:
            (A / "fx").rmdir()
    if effect_texts:
        shutil.copy2(web_dir() / "effects.js", A / "effects.js")
    else:
        (A / "effects.js").unlink(missing_ok=True)
    needed = vendor_files(effect_texts)                  # offline renders: only the libraries this project loads
    for folder in needed:
        _sync_dir(vendor_root(folder), A / "vendor" / folder)
    for d in (A / "vendor").iterdir():
        if d.name not in needed:
            shutil.rmtree(d) if d.is_dir() else d.unlink()
    for f in (proj / "compositions").glob("gx-*.html"):
        if f.stem not in ids:
            f.unlink()
    hits = hits_for(plan.graphics, cam, timed, end, {i for i in shake if any(id(b) == i for b in items if b.type == "bg")})
    hit_name, hit_vol = meta["hit_sfx"]
    cues += [(hit_name, h[0], hit_vol) for h in hits]
    pages = caption_pages(words, end, plan.captions["key"], plan.captions["max_words"])
    cfg = {"end": end, "pages": pages if mode in ("burn", "both") else [], "cam": cam, "hits": hits, "splits": splits}
    # an effect whose index.json has "aroll_fx" (topic-change) glitches the A-roll at its start: [t, dur, kind, amp] —
    # amp, the peak R / B split in px, scales with the frame (2.2 % of its width: 24 px at 1080, 42 px at 1920)
    glitch = []
    for g in items:
        fx_meta = effect_meta(found[g.params["name"]]).get("aroll_fx") if g.type == "custom" else None
        if isinstance(fx_meta, dict):
            style = ((g.params.get("params") or {}).get("style"))
            dur = fx_meta.get("dur")
            dur = float(dur) if isinstance(dur, (int, float)) and not isinstance(dur, bool) and dur > 0 else 0.6
            glitch.append([round(g.start, 3), round(min(dur, g.end - g.start), 3), "wave" if style == "wave" else "glitch",
                           round(GLITCH_AMP * W)])
    if glitch:
        cfg["glitch"] = glitch
    if cap_moves:
        cfg["cap_moves"] = cap_moves
    if shake:
        cfg["shake_hosts"] = True                      # hits shake "#shake, .cm-shake" (the bg pair with the cut-out)
    if sides:
        cfg["sides"] = sides
    if hide:
        cfg["hide"] = hide
    srt = out / "captions.srt"
    if mode in ("srt", "both"):
        srt.write_text(to_srt(pages), encoding="utf-8")
    else:
        srt.unlink(missing_ok=True)
    ch = out / "chapters.txt"
    if plan.chapters:
        ch.write_text(chapters_txt(plan.chapters, end), encoding="utf-8")
    else:
        ch.unlink(missing_ok=True)
    audio = sfx_tags(cues, end, A)
    src = pick_source(plan.music, music, out.parent)  # relative plan.music.src resolves against the recording folder
    warnings = list(plan.warnings)
    if pn and lay.mode == "classic":
        warnings.append(f"WARN theme {theme} layout is classic — the panel uses default geometry")
    if lay.mode == "split-panel" and not pn:
        warnings.append("WARN theme layout is split-panel but plan.json has no panel")
    if (music or {}).get("source") == "heygen" and not (plan.music or {}).get("src"):
        warnings.append("WARN music: config music.source is heygen but plan.json has no music.src — resolve a bed (edit skill §5) "
                        "or set music.source=none")
    vol = 0.45
    if src:
        prepare_music(src, A / "bgm" / "bed.m4a", end)
        vol = float((plan.music or {}).get("volume", (music or {}).get("volume", 0.45)))
        audio.append(f'      <audio id="music-bed" src="assets/bgm/bed.m4a" data-start="0" data-duration="{round(end, 3)}" '
                     f'data-track-index="9" data-volume="{vol}" data-audio-group="music"></audio>')
    _prune(A / "sfx", set(re.findall(r'assets/sfx/([^"]+)"', "".join(audio))))
    if src:
        _prune(A / "bgm", {"bed.m4a"})
    else:
        _prune(A / "bgm", set())
    vdur = round(min(end, duration(A / "aroll.mp4")), 3)
    (proj / "index.html").write_text(INDEX.format(lang=language, fcls="f169" if fmt == "16:9" else "f916", w=W, h=H, end=round(end, 3), vdur=vdur,
                                                  hosts="\n".join(hosts), audio="\n".join(audio), cfg=_js(cfg),
                                                  fx_head=_fx_head(effect_texts), fx_svg=FX_SVG if glitch else ""),
                                     encoding="utf-8")
    if src and not carve(proj):
        half = round(vol * 0.5, 3)
        idx = proj / "index.html"
        idx.write_text(idx.read_text(encoding="utf-8").replace(
            f'data-volume="{vol}" data-audio-group="music"', f'data-volume="{half}" data-audio-group="music"'),
            encoding="utf-8")
        print(f"WARN music: no voice carve — bed volume halved to {half}")
    checkpoints = sorted({checkpoint(g) for g in items})
    (out / "work" / "checkpoints.json").write_text(json.dumps(checkpoints), encoding="utf-8")
    return {"project": proj, "warnings": warnings, "checkpoints": checkpoints, "layout": lay.mode,
            "panel": panel_summary(plan)}
