"""plan.json + A-roll + theme pack → HyperFrames project (out/composition/).

Root index.html: A-roll inside #split > #cam > #shake, one sub-composition host per graphic, #flash, #captions,
SFX <audio> tags, and web/cutmate.js driving captions / punch-ins / hits / split moves on the main timeline.
"""
import html as _html
import json
import re
import shutil
import unicodedata
from pathlib import Path

from .cut import load_timed
from .errors import CutmateError
from .hf import ensure_project
from .media import duration
from .paths import assets_dir, theme_dir, web_dir
from .plan import Graphic, load_plan

W, H = 1080, 1920
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
    const root = document.getElementById("{cid}");
    const P = {params};
    const U = {{
      el(tag, cls, text, parent) {{ const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; (parent || root).appendChild(e); return e; }},
      counter(el, fmt) {{ const d = {{}}; let v = 0; Object.defineProperty(d, "v", {{ get: () => v, set: (n) => {{ v = n; el.textContent = fmt(n); }} }}); return d; }},
      out(target, t) {{ tl.to(target, {{ opacity: 0, y: -30, duration: 0.2, ease: "power2.in", immediateRender: false }}, Math.max(0, t)); }},
    }};
{script}
    window.__timelines["{cid}"] = tl;
  }})();</script>
</template></body></html>
"""

INDEX = """<!doctype html>
<html lang="{lang}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={w}, height={h}" />
    <title>cutmate</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
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


def _js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def _core(word: str) -> str:
    return re.sub(r"[^\w%']", "", str(word).upper())


def caption_pages(words: list[dict], end: float, key: list[str], max_words: int = 3, max_chars: int = 16,
                  pause: float = 0.35) -> list[dict]:
    pages, cur, n = [], [], 0
    for w in words:
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
        stop = min(max(nxt, start + 0.2), max(p[-1]["end"] + 0.8, start + 0.2), end - 0.01)
        ws = []
        for w in p:
            c = _core(w["word"])
            cls = "key" if c in keys else "num" if re.search(r"\d", w["word"]) else ""
            ws.append([w["word"], round(max(0.0, w["start"] - 0.04), 3), cls])
        out.append({"start": round(start, 3), "end": round(stop, 3), "words": ws})
    return out


def cam_from_cuts(timed: list[dict]) -> list[list[float]]:
    return [[round(float(s["start"]), 3), 1.0 if i % 2 == 0 else 1.12] for i, s in enumerate(timed)]


def _scale_at(cam: list[list[float]], t: float) -> float:
    s = 1.0
    for ct, cs in cam:
        if ct <= t + 1e-9:
            s = cs
    return s


def hits_for(graphics: list[Graphic], cam: list[list[float]], timed: list[dict], end: float) -> list[list[float]]:
    cuts = sorted(float(s["start"]) for s in timed)
    out = []
    for g in graphics:
        if not g.hit:
            continue
        t = g.start
        nxt = next((c for c in cuts if c > t + 1e-9), end)
        punch = min(0.5, nxt - (t + 0.12) - 0.02)
        out.append([t, _scale_at(cam, t), round(punch, 3) if punch >= 0.15 else 0])
    return out


def _sections(path: Path) -> dict:
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
        shutil.copy2(src, assets / "media" / name)
        media_map[src] = f"assets/media/{name}"
    return media_map[src]


def _copy_if_newer(src: Path, dst: Path) -> None:
    if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime or src.stat().st_size != dst.stat().st_size:
        shutil.copy2(src, dst)


def subcomp(cid: str, g: Graphic, host_start: float, theme: Path, assets: Path, media_map: dict, lang: str) -> str:
    sec = _sections(theme / "components" / f"{g.type}.html")
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
    media_tag = ""
    if g.type == "split":
        if Path(g.params["media"]).suffix.lower() in VIDEO_EXTS:
            vdur = round(min(P["end"] - P["at"], duration(Path(g.params["media"]))), 3)
            media_tag = (f'<video id="{cid}-v" class="clip" data-hf-media-start-basis="local" data-start="{P["at"]}" '
                         f'data-duration="{vdur}" src="{P["media"]}" muted playsinline></video>')
            P["kind"] = "video"
        else:
            media_tag = f'<div class="img" style="background-image:url(\'{P["media"]}\')"></div>'
            P["kind"] = "image"
    markup = _PLACEHOLDER.sub(lambda m: media_tag if m.group(1) == "media_tag"
                              else _html.escape(str(P.get(m.group(1), ""))), sec.get("markup", ""))
    return SUBCOMP.format(lang=lang, cid=cid, w=W, h=H, dur=round(g.end - host_start, 3),
                          style=sec.get("style", "").replace("ROOT", f"#{cid}"), markup=markup,
                          params=_js(P), script=sec["script"])


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


def build(out_dir: Path, theme: str = "clean", language: str = "pl", factcheck: bool = False,
          music: dict | None = None) -> dict:
    out = Path(out_dir).resolve()
    plan = load_plan(out, factcheck)
    th = theme_dir(theme)
    meta = json.loads((th / "theme.json").read_text(encoding="utf-8"))
    if not (out / "aroll.mp4").exists():
        raise CutmateError(f"{out / 'aroll.mp4'} not found — run `cutmate cut` first")
    proj = out / "composition"
    ensure_project(proj)
    A = proj / "assets"
    for d in (A / "fonts", A / "sfx", A / "media", proj / "compositions"):
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
    for i, g in enumerate(plan.graphics):
        cid = f"gx-{i + 1:02d}-{g.type}"
        ids.append(cid)
        hs = round(max(0.0, g.start - LEAD), 3)
        (proj / "compositions" / f"{cid}.html").write_text(subcomp(cid, g, hs, th, A, media_map, language),
                                                           encoding="utf-8")
        hosts.append(f'      <div id="{cid}-slot" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" '
                     f'data-start="{hs}" data-duration="{round(g.end - hs, 3)}" data-track-index="{2 + i % 2}" '
                     f'data-width="{W}" data-height="{H}"></div>')
        cues += _sfx_cues(g, meta)
    for f in (proj / "compositions").glob("gx-*.html"):
        if f.stem not in ids:
            f.unlink()
    cam = cam_from_cuts(timed)
    hits = hits_for(plan.graphics, cam, timed, end)
    hit_name, hit_vol = meta["hit_sfx"]
    cues += [(hit_name, h[0], hit_vol) for h in hits]
    splits = [[g.start, round(max(g.start + 0.45, g.end - 0.4), 3)] for g in plan.graphics if g.type == "split"]
    cfg = {"end": end, "pages": caption_pages(words, end, plan.captions["key"], plan.captions["max_words"]),
           "cam": cam, "hits": hits, "splits": splits}
    audio = sfx_tags(cues, end, A)
    vdur = round(min(end, duration(A / "aroll.mp4")), 3)
    (proj / "index.html").write_text(INDEX.format(lang=language, w=W, h=H, end=round(end, 3), vdur=vdur,
                                                  hosts="\n".join(hosts), audio="\n".join(audio), cfg=_js(cfg)),
                                     encoding="utf-8")
    checkpoints = sorted({round(min(g.start + 0.4, g.end - 0.05), 2) for g in plan.graphics})
    (out / "work" / "checkpoints.json").write_text(json.dumps(checkpoints), encoding="utf-8")
    return {"project": proj, "warnings": plan.warnings, "checkpoints": checkpoints}
