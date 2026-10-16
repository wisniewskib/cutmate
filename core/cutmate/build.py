"""plan.json + A-roll + theme pack → HyperFrames project (out/composition/).

Root index.html: A-roll inside #split > #cam > #shake, one sub-composition host per graphic, #flash, #captions,
SFX <audio> tags, and web/cutmate.js driving captions / punch-ins / hits / split moves on the main timeline.
"""
import html as _html
import json
import os
import re
import shutil
import unicodedata
from pathlib import Path

from .captions import to_srt
from .chapters import chapters_txt
from .config import CAPTION_MODES, DEFAULT_CAPTIONS
from .cut import load_timed
from .effects import find_effect, libs_head, lint_effect, track_slice
from .errors import CutmateError
from .formats import size_of
from .hf import ensure_project, hf
from .media import duration, run
from .music import carve, pick_source, prepare_music
from .paths import assets_dir, plugin_root, theme_dir, web_dir
from .plan import PLATE, Graphic, load_plan, plate_chapters
from .tracks import pick_hand

CHAPTER_LABEL = {"pl": "ROZDZIAŁ", "en": "CHAPTER"}
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

INDEX = """<!doctype html>
<html lang="{lang}" class="{fcls}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={w}, height={h}" />
    <title>cutmate</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>{fx_head}
    <link rel="stylesheet" href="assets/tokens.css" />
    <link rel="stylesheet" href="assets/theme.css" />
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{end}" data-width="{w}" data-height="{h}">
      <div id="split"><div id="cam"><div id="shake"><video id="aroll" src="assets/aroll.mp4" data-start="0" data-duration="{vdur}" data-media-start="0" data-track-index="0" playsinline data-has-audio="true"></video></div></div></div>
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


def _scale_at(cam: list[list[float]], t: float) -> float:
    s = 1.0
    for c in cam:
        if c[0] <= t + 1e-9:
            s = c[1]
    return s


def hits_for(graphics: list[Graphic], cam: list[list[float]], timed: list[dict], end: float) -> list[list[float]]:
    bgs = [(g.start, g.end) for g in graphics if g.type == "bg"]
    cuts = sorted([float(s["start"]) for s in timed] + [t for r in bgs for t in r])  # camera changes end a punch
    out = []
    for g in graphics:
        if not g.hit:
            continue
        t = g.start
        nxt = next((c for c in cuts if c > t + 1e-9), end)
        punch = min(0.5, nxt - (t + 0.12) - 0.02)
        if any(a - 1e-9 <= t < b for a, b in bgs):
            punch = 0                                    # no punch-in over a bg cut-out (shake only)
        out.append([t, _scale_at(cam, t), round(punch, 3) if punch >= 0.15 else 0])
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


FALLBACK = ("bg", "side", "chapter", "pip", "lower-third")  # components newer than many user themes


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


def subcomp(cid: str, g: Graphic, host_start: float, theme: Path, assets: Path, media_map: dict, lang: str,
            size: tuple = (1080, 1920), extra_tags: dict | None = None, comp_path: Path | None = None,
            tracks: dict | None = None, assets_url: str | None = None) -> str:
    sec = _sections(comp_path or theme / "components" / f"{g.type}.html")
    W, H = size
    loc = lambda t: round(max(0.0, t - host_start), 3)  # noqa: E731
    P = {k: v for k, v in g.params.items()}
    P.update(at=loc(g.start), end=loc(g.end), lang=lang)
    if g.type == "list":
        P["items"] = [{"text": it["text"], "at": loc(it["at"])} for it in g.params["items"]]
    if g.type == "bars":
        P["note"] = ILLUSTRATIVE.get(lang, ILLUSTRATIVE["en"]) if g.params.get("illustrative") else ""
    for k in ("media", "image", "logo", "icon"):
        if k in P:
            P[k] = _copy_media(g.params[k], assets, media_map)
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
                     for t, x, y in track_slice(tracks["tracks"].get(tn, []), g.start, g.end, host_start, W, H)]
        P = dict(g.params.get("params") or {})          # user params first: timing / size keys always win
        P.update(name=g.params["name"], at=loc(g.start), end=loc(g.end), lang=lang, w=rw, h=rh,
                 dur=round(g.end - host_start, 3), track=track)
        if assets_url:
            P["assets"] = assets_url
        u_open, u_close = FX_OPEN.format(cid=cid), ")"
        if region:
            root = f'document.querySelector("#{cid} > .cm-region")'
        if g.params.get("_fade"):
            fade = FADE.format(f=g.params["_fade"])
    media_tag = ""
    if g.type in ("split", "pip"):
        P["fit"] = g.params.get("fit", "contain")
        media_tag = _media_tag(cid, g, P)
    if g.type == "side":
        P["side"] = "l" if g.params["speaker"] == "right" else "r"
        P["fit"] = g.params.get("fit", "cover")
        if "media" in g.params:
            media_tag = _media_tag(cid, g, P)
        else:
            P["side"] += " side-fx"
    back_tag = _media_tag(cid, g, P) if g.type == "bg" and "media" in g.params else ""
    tags = {"media_tag": media_tag, "back_tag": back_tag, **(extra_tags or {})}
    markup = _PLACEHOLDER.sub(lambda m: tags[m.group(1)] if m.group(1) in tags
                              else _html.escape(str(P.get(m.group(1), ""))), sec.get("markup", ""))
    if region:
        markup = REGION.format(x=region[0], y=region[1], w=region[2], h=region[3], markup=markup)
    return SUBCOMP.format(lang=lang, cid=cid, w=W, h=H, dur=round(g.end - host_start, 3), root=root, u_open=u_open,
                          u_close=u_close, fade=fade, style=sec.get("style", "").replace("ROOT", f"#{cid}"),
                          markup=markup, params=_js(P), script=sec["script"])


def _sfx_cues(g: Graphic, meta: dict) -> list[tuple]:
    if g.sfx is False:
        return []
    if isinstance(g.sfx, str):
        return [(g.sfx, g.start, 0.35)]
    cues = [(n, g.start + off, vol) for n, off, vol in meta["sfx"].get(g.type, [])]
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
    """Full-screen plates for chapters 2+ (chapter 1 is the start of the video)."""
    word = CHAPTER_LABEL.get(lang, CHAPTER_LABEL["en"])
    return [Graphic("chapter", c["start"], round(min(c["start"] + PLATE, end - 0.05), 3),
                    {"num": c["num"], "title": c["title"], "label": f"{word} {c['num']:02d}"}, False, None, -1)
            for c in plate_chapters(plan.chapters, end)]


def build(out_dir: Path, theme: str = "clean", language: str = "pl", factcheck: bool = False,
          music: dict | None = None, captions: dict | None = None) -> dict:
    out = Path(out_dir).resolve()
    plan = load_plan(out, factcheck)
    fmt = plan.format
    W, H = size_of(fmt)
    mode = (captions or {}).get(fmt) or DEFAULT_CAPTIONS[fmt]
    if mode not in CAPTION_MODES:
        raise CutmateError(f"unknown caption mode {mode!r} for {fmt} (use {', '.join(CAPTION_MODES)})")
    th = theme_dir(theme)
    meta = _theme_meta(th)
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
    for i, g in enumerate(items):
        cid = f"gx-{i + 1:02d}-{g.type}"
        ids.append(cid)
        hs = round(max(0.0, g.start - LEAD), 3)
        extra = None
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
        if g.type == "bg":
            name = bg_cutout(A / "aroll.mp4", g.start, g.end, A / "media")
            keep_media.add(name)
            loc_at = round(g.start - hs, 3)
            extra = {"cut_tag": f'<video id="{cid}-c" class="clip" data-hf-media-start-basis="local" data-start="{loc_at}" '
                                f'data-duration="{round(g.end - g.start, 3)}" src="assets/media/{name}" muted playsinline></video>'}
        assets_url = None
        if g.type == "custom":
            comp_path = find_effect(g.params["name"], out, theme)
            lint_effect(comp_path)
            effect_texts.append(comp_path.read_text(encoding="utf-8"))
            folder = comp_path.parent / g.params["name"]     # the effect's own files (Lottie JSON, textures…)
            if folder.is_dir():
                _sync_dir(folder, A / "fx" / g.params["name"])
                fx_used.add(g.params["name"])
                assets_url = f"assets/fx/{g.params['name']}/"
        else:
            comp_path = _component(th, g.type, theme, warned)
        (proj / "compositions" / f"{cid}.html").write_text(
            subcomp(cid, g, hs, th, A, media_map, language, size=(W, H), extra_tags=extra, comp_path=comp_path,
                    tracks=tr, assets_url=assets_url), encoding="utf-8")
        hosts.append(f'      <div id="{cid}-slot" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" '
                     f'data-start="{hs}" data-duration="{round(g.end - hs, 3)}" data-track-index="{2 + i % 2}" '
                     f'data-width="{W}" data-height="{H}"></div>')
        cues += _sfx_cues(g, meta)
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
    for f in (proj / "compositions").glob("gx-*.html"):
        if f.stem not in ids:
            f.unlink()
    cam = cam_from_cuts(timed, fmt, plan.face, [(g.start, g.end) for g in plan.graphics if g.type == "bg"])
    hits = hits_for(plan.graphics, cam, timed, end)
    hit_name, hit_vol = meta["hit_sfx"]
    cues += [(hit_name, h[0], hit_vol) for h in hits]
    splits = [[g.start, round(max(g.start + 0.45, g.end - 0.4), 3)] for g in plan.graphics if g.type == "split"]
    pages = caption_pages(words, end, plan.captions["key"], plan.captions["max_words"])
    sides = [[g.start, round(max(g.start + 0.45, g.end - 0.4), 3),
              round((1440 if g.params["speaker"] == "right" else 480) - plan.face.get(_seg_at(timed, g.start), FACE_DEFAULT)[0] * W)]
             for g in plan.graphics if g.type == "side"]
    cfg = {"end": end, "pages": pages if mode in ("burn", "both") else [], "cam": cam, "hits": hits, "splits": splits}
    if sides:
        cfg["sides"] = sides
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
    vol = 0.45
    if src:
        prepare_music(src, A / "bgm" / "bed.m4a", end)
        vol = float((plan.music or {}).get("volume", 0.45))
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
                                                  fx_head=_fx_head(effect_texts)),
                                     encoding="utf-8")
    if src and not carve(proj):
        half = round(vol * 0.5, 3)
        idx = proj / "index.html"
        idx.write_text(idx.read_text(encoding="utf-8").replace(
            f'data-volume="{vol}" data-audio-group="music"', f'data-volume="{half}" data-audio-group="music"'),
            encoding="utf-8")
        print(f"WARN music: no voice carve — bed volume halved to {half}")
    def checkpoint(g: Graphic) -> float:
        t = max(it["at"] for it in g.params["items"]) if g.type == "list" else g.start
        return round(min(t + 0.4, g.end - 0.05), 2)
    checkpoints = sorted({checkpoint(g) for g in items})
    (out / "work" / "checkpoints.json").write_text(json.dumps(checkpoints), encoding="utf-8")
    return {"project": proj, "warnings": plan.warnings, "checkpoints": checkpoints}
