"""Effects written on request (custom components): where they live, what they may not use, which libraries they need."""
import json
import re
import shutil
from pathlib import Path

from .config import home
from .errors import CutmateError, PlanError
from .paths import plugin_root

FORBIDDEN = ("Date.now", "Math.random", "performance.now", "requestAnimationFrame", "setTimeout", "setInterval",
             "onUpdate", "setAnimationLoop", "anime.utils.random", "d3.transition", "AfterimagePass")
_SECTION = re.compile(r"<(style|markup|script)>(.*?)</\1>", re.S)
GSAP = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/"
THREE = "https://cdn.jsdelivr.net/npm/three@0.181.2/"
LIBS = [  # (marker, html)
    (r"\banime\.|U\.anime\(", '<script src="https://cdn.jsdelivr.net/npm/animejs@4.5.0/dist/bundles/anime.umd.min.js"></script>'),
    (r"\blottie\.|U\.lottie\(", '<script src="https://cdnjs.cloudflare.com/ajax/libs/bodymovin/5.12.2/lottie.min.js"></script>'),
    (r"\bkatex\.|U\.tex\(", '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.19.0/dist/katex.min.css" />'
                           '<script src="https://cdn.jsdelivr.net/npm/katex@0.19.0/dist/katex.min.js"></script>'),
    (r"\brough\.|U\.rough\(", '<script src="https://cdn.jsdelivr.net/npm/roughjs@4.6.6/bundled/rough.js"></script>'),
    (r"\bd3\.", '<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>'),
]
PLUGINS = [(r"drawSVG|U\.draw\(", "DrawSVGPlugin"), (r"morphSVG", "MorphSVGPlugin"),
           (r"motionPath", "MotionPathPlugin"), (r"\bSplitText\b", "SplitText")]
THREE_MARK = r"\bTHREE\b|U\.three\(|U\.glowOrb\(|['\"]three['\"]"


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


def lint_effect(path: Path) -> None:
    text = Path(path).read_text(encoding="utf-8")
    if "script" not in dict(_SECTION.findall(text)):
        raise PlanError(f"{Path(path).name}: effect has no <script> section")
    for api in FORBIDDEN:
        if api in text:
            raise PlanError(f"{Path(path).name}: uses {api} — not allowed in effects (see SKILL.md, effects rules)")


def libs_head(texts: list[str]) -> str:
    blob = "\n".join(texts)
    parts = []
    if re.search(THREE_MARK, blob):
        parts.append('<script type="importmap">{"imports":{"three":"' + THREE + 'build/three.module.js",'
                     '"three/addons/":"' + THREE + 'examples/jsm/"}}</script>')
    parts += [html for mark, html in LIBS if re.search(mark, blob)]
    plugins = [name for mark, name in PLUGINS if re.search(mark, blob)]
    parts += [f'<script src="{GSAP}{p}.min.js"></script>' for p in plugins]
    if plugins:
        parts.append(f"<script>gsap.registerPlugin({', '.join(plugins)});</script>")
    return "\n    ".join(parts)


def track_slice(samples, a: float, b: float, host_start: float, W: int, H: int) -> list[list[float]]:
    return [[round(t - host_start, 3), round(x * W, 1), round(y * H, 1)] for t, x, y, *_ in samples if a <= t <= b]


def save_effect(out_dir: Path, name: str, theme: str = "clean", description: str = "", force: bool = False) -> Path:
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
        used = [g for g in json.loads(plan.read_text(encoding="utf-8")).get("graphics", [])
                if g.get("type") == "custom" and g.get("name") == name]
        if used:
            params, follow = list(used[-1].get("params") or {}), used[-1].get("follow")
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    index = dest_dir / "index.json"
    entries = json.loads(index.read_text(encoding="utf-8")) if index.exists() else []
    entries = [e for e in entries if e.get("name") != name]
    entries.append({"name": name, "description": description, "params": params, "follow": follow})
    entries.sort(key=lambda e: e["name"])
    index.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest
