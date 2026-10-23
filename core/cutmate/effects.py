"""Effects written on request (custom components): where they live, what they may not use, which libraries they need."""
import json
import re
import shutil
from pathlib import Path

from .config import home
from .errors import CutmateError, PlanError
from .paths import plugin_root, vendor_dir
from .plan import NAME_RE

FORBIDDEN = ("Date.now", "Math.random", "performance.now", "requestAnimationFrame", "setTimeout", "setInterval",
             "onUpdate", "setAnimationLoop", "anime.utils.random", "d3.transition", "AfterimagePass",
             "THREE.Clock", "new Date", "crypto.getRandomValues", "gsap.ticker", ".play(",
             # callbacks fire only when playback crosses a point (a worker seeking straight to a frame skips them);
             # GlitchEffect / ScrambleTextPlugin draw from Math.random inside the library
             "onComplete", "onRepeat", "onRender", "onBegin", "onLoop", ".restart(", "GlitchEffect", "ScrambleTextPlugin",
             "onStart", "onReverseComplete", "onBeforeUpdate")
_SECTION = re.compile(r"<(style|markup|script)>(.*?)</\1>", re.S)
VENDOR = {"gsap": "gsap@3.14.2", "three": "three@0.181.2", "postprocessing": "postprocessing@6.39.5",
          "animejs": "animejs@4.5.0", "lottie": "lottie@5.12.2", "katex": "katex@0.19.0", "roughjs": "roughjs@4.6.6",
          "d3": "d3@7.9.0"}                              # name -> assets/vendor folder (tools/vendor_libs.py writes them)
VENDOR_URL = "assets/vendor/"                            # the same, as seen from index.html (P.vendor in every custom effect)
GSAP = f"{VENDOR_URL}{VENDOR['gsap']}/dist/"
THREE = f"{VENDOR_URL}{VENDOR['three']}/"
POST = f"{VENDOR_URL}{VENDOR['postprocessing']}/build/index.js"
LIBS = [  # (marker, vendor name, html)
    (r"\banime\.|U\.anime\(", "animejs", f'<script src="{VENDOR_URL}{VENDOR["animejs"]}/dist/bundles/anime.umd.min.js"></script>'),
    (r"\blottie\.|U\.lottie\(", "lottie", f'<script src="{VENDOR_URL}{VENDOR["lottie"]}/build/player/lottie.min.js"></script>'),
    (r"\bkatex\.|U\.tex\(", "katex", f'<link rel="stylesheet" href="{VENDOR_URL}{VENDOR["katex"]}/dist/katex.min.css" />'
                                      f'<script src="{VENDOR_URL}{VENDOR["katex"]}/dist/katex.min.js"></script>'),
    (r"\brough\.|U\.rough\(", "roughjs", f'<script src="{VENDOR_URL}{VENDOR["roughjs"]}/bundled/rough.js"></script>'),
    (r"\bd3\.", "d3", f'<script src="{VENDOR_URL}{VENDOR["d3"]}/dist/d3.min.js"></script>'),
]
PLUGINS = [(r"drawSVG|U\.draw\(", "DrawSVGPlugin"), (r"morphSVG", "MorphSVGPlugin"),
           (r"motionPath", "MotionPathPlugin"), (r"\bSplitText\b", "SplitText")]
THREE_MARK = r"\bTHREE\b|U\.three\(|U\.glowOrb\(|['\"]three['\"]"
POST_MARK = r"U\.post\(|['\"]postprocessing['\"]"      # postprocessing implies three


def find_effect(name: str, out_dir: Path, theme: str) -> Path:
    places = [Path(out_dir) / "custom" / f"{name}.html",
              home() / "themes" / theme / "components" / "custom" / f"{name}.html",
              plugin_root() / "themes" / theme / "components" / "custom" / f"{name}.html",
              plugin_root() / "themes" / "clean" / "components" / "custom" / f"{name}.html"]  # stock effects
    places = list(dict.fromkeys(places))
    for p in places:
        if p.exists():
            return p
    raise PlanError(f"effect {name!r} not found — write {places[0]} (also looked in {', '.join(map(str, places[1:]))})")


_THREE_ADDON = re.compile(r"""three/addons/([^"'`\s)]+)""")


def three_addons() -> list[str]:
    """The three.js addons cutmate vendors (paths under examples/jsm/, the importmap's three/addons/), sorted."""
    jsm = vendor_root(VENDOR["three"]) / "examples" / "jsm"
    return sorted(p.relative_to(jsm).as_posix() for p in jsm.rglob("*.js"))


def lint_effect(path: Path) -> None:
    text = Path(path).read_text(encoding="utf-8")
    if "script" not in dict(_SECTION.findall(text)):
        raise PlanError(f"{Path(path).name}: effect has no <script> section")
    for api in FORBIDDEN:
        if api in text:
            raise PlanError(f"{Path(path).name}: uses {api} — not allowed in effects (see SKILL.md, effects rules)")
    wanted = _THREE_ADDON.findall(text)
    if wanted:                                         # only the vendored addons exist offline (no CDN fallback)
        have = three_addons()
        for addon in wanted:
            if addon not in have:
                raise PlanError(f"{Path(path).name}: imports three/addons/{addon}, which cutmate does not bundle — "
                                f"use one of: {', '.join(have)}")


def effect_meta(path: Path) -> dict:
    """The effect's entry (`name` = the file stem) in the index.json beside it: build needs such as "kind", "modes",
    "tips", "aroll_fx", "webgl". {} when there is no index.json, it cannot be read or it has no entry for the effect."""
    path = Path(path)
    try:
        entries = json.loads((path.parent / "index.json").read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    if not isinstance(entries, list):
        return {}
    return next((dict(e) for e in entries if isinstance(e, dict) and e.get("name") == path.stem), {})


def vendor_root(folder: str) -> Path:
    """The vendored folder `<name>@<version>`: bundled in assets/vendor, else downloaded by setup into $CUTMATE_HOME/vendor
    (gsap: its licence does not clearly allow redistribution, so setup fetches it, sha-checked)."""
    for base in (vendor_dir(), home() / "vendor"):
        if (base / folder).is_dir():
            return base / folder
    raise CutmateError(f"vendored library {folder} not found (looked in {vendor_dir()} and {home() / 'vendor'}) — "
                       'run "$CM" vendor (or /cutmate:setup)')


def vendor_files(texts: list[str]) -> list[str]:
    """The vendor folder names the given composition texts need (`gsap` is in every index.html)."""
    blob = "\n".join(texts)
    post = bool(re.search(POST_MARK, blob))
    names = ["gsap"]
    if post or re.search(THREE_MARK, blob):
        names.append("three")
    if post:
        names.append("postprocessing")
    names += [name for mark, name, _ in LIBS if re.search(mark, blob)]
    return [VENDOR[n] for n in names]


def libs_head(texts: list[str]) -> str:
    blob = "\n".join(texts)
    parts = []
    post = bool(re.search(POST_MARK, blob))
    if post or re.search(THREE_MARK, blob):
        # an import map address must be a URL, not a bare specifier: "./" makes it relative to index.html
        imports = {"three": "./" + THREE + "build/three.module.min.js", "three/addons/": "./" + THREE + "examples/jsm/"}
        if post:
            imports["postprocessing"] = "./" + POST
        parts.append('<script type="importmap">' + json.dumps({"imports": imports}, separators=(",", ":")) + "</script>")
    parts += [html for mark, _, html in LIBS if re.search(mark, blob)]
    plugins = [name for mark, name in PLUGINS if re.search(mark, blob)]
    parts += [f'<script src="{GSAP}{p}.min.js"></script>' for p in plugins]
    if plugins:
        parts.append(f"<script>gsap.registerPlugin({', '.join(plugins)});</script>")
    return "\n    ".join(parts)


def track_slice(samples, a: float, b: float, host_start: float, W: int, H: int, to_px=None) -> list[list[float]]:
    """Samples in [a, b] as [local t, x px, y px]; to_px(x, y, t) maps a frame point to screen px (camera, offsets)."""
    to_px = to_px or (lambda x, y, t: (round(x * W, 1), round(y * H, 1)))
    return [[round(t - host_start, 3), *to_px(x, y, t)] for t, x, y, *_ in samples if a <= t <= b]


def held_slice(samples, a: float, b: float, host_start: float, W: int, H: int, to_px=None,
               step: float = 0.4, ease: float = 0.3) -> list[list[float]]:
    """Like track_slice, but never empty inside [a, b] while the track has any sample: starts at a with the nearest
    sample (so an effect shows at once, not when the hand is next seen), holds the last position through gaps (moving to
    the next one over the last `ease` s) and to b, with points <= step apart (U.trackAt never blanks)."""
    if not samples:
        return []
    to_px = to_px or (lambda x, y, t: (round(x * W, 1), round(y * H, 1)))
    inside = [s[:3] for s in samples if a <= s[0] <= b]
    if not inside or inside[0][0] > a:
        near = min(samples, key=lambda s: (abs(s[0] - a), s[0] > a))
        inside.insert(0, [a, near[1], near[2]])
    if inside[-1][0] < b:
        inside.append([b, inside[-1][1], inside[-1][2]])
    pts = [inside[0]]
    for p, q in zip(inside, inside[1:]):
        if q[0] - p[0] > step:                          # hold p, then glide to q
            hold_to = max(p[0], q[0] - ease)
            t = p[0] + step
            while t < hold_to - 1e-9:
                pts.append([t, p[1], p[2]])
                t += step
            if hold_to > p[0] + 1e-9:
                pts.append([hold_to, p[1], p[2]])
        pts.append(q)
    return [[round(t - host_start, 3), *to_px(x, y, t)] for t, x, y in pts]


TIP_HOLD = 0.25    # a fingertip that is not seen any more is held this long, then marked not extended


def tip_slice(samples, a: float, b: float, host_start: float, W: int, H: int, to_px=None) -> list[list[float]]:
    """Fingertip samples in [a, b] as [local t, x px, y px, ext] (ext 1.0 extended / 0.0). Like held_slice it starts at a
    (with the nearest sample, its ext kept only when that sample is <= TIP_HOLD s away), but a finger is never held
    longer than TIP_HOLD s: TIP_HOLD s after the last sight before a longer gap (or the end of the track) a sample with
    ext 0.0 marks it gone, so no sparks come from a missing finger."""
    if not samples:
        return []
    to_px = to_px or (lambda x, y, t: (round(x * W, 1), round(y * H, 1)))
    on = lambda e: 1.0 if e >= 0.5 else 0.0  # noqa: E731
    inside = [[s[0], s[1], s[2], on(s[3]), s[0]] for s in samples if a <= s[0] <= b]    # [t, x, y, ext, last sight]
    if not inside or inside[0][0] > a:
        near = min(samples, key=lambda s: (abs(s[0] - a), s[0] > a))
        held = abs(near[0] - a) <= TIP_HOLD + 1e-9
        inside.insert(0, [a, near[1], near[2], on(near[3]) if held else 0.0, near[0] if held else a])
    pts = []
    for p, q in zip(inside, inside[1:] + [[b + TIP_HOLD + 1, *inside[-1][1:]]]):
        pts.append(p[:4])
        off = max(p[0], p[4] + TIP_HOLD)                 # TIP_HOLD after the real last sight (not after a)
        if q[0] - off > 1e-9 and off <= b + 1e-9:
            pts.append([off, p[1], p[2], 0.0])
    return [[round(t - host_start, 3), *to_px(x, y, t), e] for t, x, y, e in pts]


THEME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        raise CutmateError(f"{path}: cannot read ({' '.join(str(e).split())})") from None


def save_effect(out_dir: Path, name: str, theme: str = "clean", description: str = "", force: bool = False) -> Path:
    if not NAME_RE.match(str(name)):
        raise CutmateError(f"bad effect name {name!r}: lowercase letters, digits and dashes (e.g. energy-ball)")
    if not THEME_RE.match(str(theme)):
        raise CutmateError(f"bad theme name {theme!r}: letters, digits, _ and - only")
    out_dir = Path(out_dir)
    src = out_dir / "custom" / f"{name}.html"
    if not src.exists():
        raise CutmateError(f"effect {name!r} not found — expected {src}")
    lint_effect(src)
    dest_dir = home() / "themes" / theme / "components" / "custom"
    dest = dest_dir / f"{name}.html"
    if dest.exists() and not force:
        raise CutmateError(f"effect {name} already saved in theme {theme} — use --force to replace it")
    params, follow = [], None
    plan = out_dir / "plan.json"
    if plan.exists():
        raw = _read_json(plan)
        gs = raw.get("graphics") if isinstance(raw, dict) else None
        used = [g for g in gs if isinstance(g, dict) and g.get("type") == "custom" and g.get("name") == name] \
            if isinstance(gs, list) else []
        if used:
            p = used[-1].get("params")
            params, follow = list(p) if isinstance(p, dict) else [], used[-1].get("follow")
    index = dest_dir / "index.json"
    entries = _read_json(index) if index.exists() else []
    if not isinstance(entries, list):
        raise CutmateError(f"{index}: must be a JSON list — fix or delete it")
    entries = [e for e in entries if isinstance(e, dict)]
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    folder, dest_folder = src.parent / name, dest_dir / name    # the effect's own files (Lottie JSON, textures…)
    if dest_folder.exists():
        shutil.rmtree(dest_folder)
    if folder.is_dir():
        shutil.copytree(folder, dest_folder)
    entries = [e for e in entries if e.get("name") != name]
    entries.append({"name": name, "description": description, "params": params, "follow": follow})
    entries.sort(key=lambda e: str(e.get("name", "")))
    index.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest
